import io
import wave

import pytest

from tts import piper_tts
from tts.piper_tts import Speaker

RATE = 22050


class FakeVoice:
    calls = []

    @classmethod
    def load(cls, path):
        return cls()

    def synthesize_wav(self, text, wf):
        FakeVoice.calls.append(text)
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(b"\x01\x00" * 100)


@pytest.fixture
def speaker(tmp_path, monkeypatch):
    FakeVoice.calls = []
    played = []
    monkeypatch.setattr(piper_tts, "PiperVoice", FakeVoice)
    monkeypatch.setattr(piper_tts.winsound, "PlaySound",
                        lambda data, flags: played.append(data))
    voice = tmp_path / "v.onnx"
    voice.write_text("")
    s = Speaker(str(voice), lead_silence=0.1)
    s.played = played
    return s


def test_missing_voice_file():
    with pytest.raises(FileNotFoundError):
        Speaker(r"C:\definitely\missing.onnx")


def test_lead_silence_is_prepended(speaker):
    data = speaker._render("hi")
    with wave.open(io.BytesIO(data), "rb") as r:
        silence = int(RATE * 0.1)
        assert r.getnframes() == silence + 100
        frames = r.readframes(r.getnframes())
    assert frames[: silence * 2] == b"\x00" * (silence * 2)
    assert frames[silence * 2:][:2] == b"\x01\x00"


def test_say_plays_and_caches(speaker):
    speaker.say("hello")
    speaker.say("hello")
    assert FakeVoice.calls == ["hello"]          # synthesized once
    assert len(speaker.played) == 2              # played twice


def test_empty_text_is_ignored(speaker):
    speaker.say("   ")
    speaker.say("")
    assert speaker.played == [] and FakeVoice.calls == []


def test_warm_up_caches_without_playing(speaker):
    speaker.warm_up(["a", "b"])
    assert speaker.played == []
    speaker.say("a")
    assert FakeVoice.calls == ["a", "b"]


def test_cache_evicts_oldest(speaker, monkeypatch):
    monkeypatch.setattr(piper_tts, "CACHE_SIZE", 2)
    for text in ("a", "b", "c"):
        speaker.say(text)
    assert list(speaker._cache) == ["b", "c"]