from types import SimpleNamespace

import numpy as np

from stt import whisper_engine
from stt.whisper_engine import WhisperSTT

AUDIO = np.zeros(16000, dtype="float32")


class FakeModel:
    def __init__(self, probs, segments):
        self.probs, self.segments = probs, segments
        self.kwargs = None

    def detect_language(self, audio):
        return None, None, self.probs

    def transcribe(self, audio, **kwargs):
        self.kwargs = kwargs
        return iter(self.segments), None


def make_stt(probs, segments):
    stt = WhisperSTT.__new__(WhisperSTT)
    stt.model = FakeModel(probs, segments)
    stt.prompt = "PROMPT"
    return stt


def seg(text, no_speech=0.0):
    return SimpleNamespace(text=text, no_speech_prob=no_speech)


def test_normal_phrase():
    stt = make_stt([("en", 0.9), ("uk", 0.1)], [seg(" Open Battle.net ")])
    assert stt.transcribe(AUDIO) == ("Open Battle.net", "en")


def test_segments_are_joined():
    stt = make_stt([("en", 0.9)], [seg("Open"), seg("Steam")])
    assert stt.transcribe(AUDIO)[0] == "Open Steam"


def test_prompt_and_language_are_passed():
    stt = make_stt([("uk", 0.9)], [seg("привіт")])
    stt.transcribe(AUDIO)
    assert stt.model.kwargs["initial_prompt"] == "PROMPT"
    assert stt.model.kwargs["language"] == "uk"
    assert stt.model.kwargs["condition_on_previous_text"] is False


def test_hallucination_is_dropped():
    stt = make_stt([("en", 0.9)], [seg("That's all for this video, thanks for watching.")])
    assert stt.transcribe(AUDIO)[0] == ""


def test_no_speech_segments_are_dropped():
    stt = make_stt([("en", 0.9)], [seg("Hello", no_speech=0.9)])
    assert stt.transcribe(AUDIO)[0] == ""


def test_language_limited_to_allowed():
    stt = make_stt([("pl", 0.9), ("uk", 0.05), ("en", 0.04)], [seg("відкрий")])
    assert stt.transcribe(AUDIO)[1] == "uk"


def test_language_fallback_when_none_allowed():
    stt = make_stt([("pl", 1.0)], [seg("x")])
    assert stt.transcribe(AUDIO)[1] == "en"


def test_priority_changes_choice(monkeypatch):
    monkeypatch.setitem(whisper_engine.PRIORITY, "uk", 3.0)
    stt = make_stt([("en", 0.5), ("uk", 0.3)], [seg("x")])
    assert stt.transcribe(AUDIO)[1] == "uk"


def test_too_short_audio_returns_empty():
    stt = make_stt([("en", 0.9)], [seg("Hello")])
    assert stt.transcribe(np.zeros(100, dtype="float32")) == ("", "en")
    assert stt.transcribe(None) == ("", "en")


def test_prompt_built_from_app_names(monkeypatch):
    monkeypatch.setattr(whisper_engine, "WhisperModel", lambda *a, **k: object())
    assert WhisperSTT(app_names=["Foo", "Bar"]).prompt.endswith("Foo Bar")
    assert "Warcraft" in WhisperSTT().prompt