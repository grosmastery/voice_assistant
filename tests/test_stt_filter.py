from types import SimpleNamespace

import numpy as np

from stt.whisper_engine import WhisperSTT

AUDIO = np.zeros(16000, dtype="float32")


class FakeModel:
    def __init__(self, probs, segments):
        self.probs, self.segments = probs, segments

    def detect_language(self, audio):
        return None, None, self.probs

    def transcribe(self, audio, **kwargs):
        return iter(self.segments), None


def make_stt(probs, segments):
    stt = WhisperSTT.__new__(WhisperSTT)
    stt.model = FakeModel(probs, segments)
    stt.prompt = ""
    return stt


def seg(text, no_speech=0.0):
    return SimpleNamespace(text=text, no_speech_prob=no_speech)


def test_normal_phrase():
    stt = make_stt([("en", 0.9), ("uk", 0.1)], [seg(" Open Battle.net ")])
    assert stt.transcribe(AUDIO) == ("Open Battle.net", "en")


def test_hallucination_is_dropped():
    stt = make_stt([("en", 0.9)],
                   [seg("That's all for this video, thanks for watching.")])
    text, _ = stt.transcribe(AUDIO)
    assert text == ""


def test_no_speech_segments_are_dropped():
    stt = make_stt([("en", 0.9)], [seg("Hello", no_speech=0.9)])
    assert stt.transcribe(AUDIO)[0] == ""


def test_language_limited_to_allowed():
    stt = make_stt([("pl", 0.9), ("uk", 0.05), ("en", 0.04)], [seg("відкрий")])
    assert stt.transcribe(AUDIO)[1] == "uk"