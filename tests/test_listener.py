import numpy as np

from audio.listener import FRAME, VoiceListener


class FakeVad:
    def is_speech(self, buf, rate):
        return any(buf)                      # ненульовий звук = мова


class FakeStream:
    def __init__(self, frames):
        self.frames = iter(frames)

    def read(self, n):
        return next(self.frames).reshape(-1, 1), False


def speech():
    return np.ones(FRAME, dtype="int16")


def quiet():
    return np.zeros(FRAME, dtype="int16")


def make_listener(**kw):
    l = VoiceListener.__new__(VoiceListener)
    l.vad = FakeVad()
    l.silence_sec = kw.get("silence_sec", 0.4)
    l.no_speech_sec = kw.get("no_speech_sec", 0.4)
    l.max_sec = kw.get("max_sec", 10.0)
    return l


def test_phrase_recorded_until_silence():
    stream = FakeStream([speech()] * 3 + [quiet()] * 20)
    audio = make_listener()._record_phrase(stream)
    assert audio is not None
    assert audio.dtype == np.float32
    assert 3 * FRAME <= len(audio) < 12 * FRAME


def test_silence_only_returns_none():
    stream = FakeStream([quiet()] * 50)
    assert make_listener()._record_phrase(stream) is None


def test_max_length_is_respected():
    stream = FakeStream([speech()] * 200)
    audio = make_listener(max_sec=1.0)._record_phrase(stream)
    assert len(audio) <= 14 * FRAME