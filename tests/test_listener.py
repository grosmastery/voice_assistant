import numpy as np

from audio import listener as lst
from audio.listener import FRAME, VoiceListener


class FakeVad:
    def is_speech(self, buf, rate):
        return any(buf)                      # non-zero audio = speech


class FakeStream:
    def __init__(self, frames):
        self.frames = iter(frames)

    def read(self, n):
        return next(self.frames).reshape(-1, 1), False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def speech():
    return np.ones(FRAME, dtype="int16")


def quiet():
    return np.zeros(FRAME, dtype="int16")


def make_listener(**kw):
    l = VoiceListener.__new__(VoiceListener)
    l.vad = FakeVad()
    l.threshold = kw.get("threshold", 0.5)
    l.silence_sec = kw.get("silence_sec", 0.4)
    l.no_speech_sec = kw.get("no_speech_sec", 0.4)
    l.max_sec = kw.get("max_sec", 10.0)
    return l


# ---- _record_phrase ----
def test_phrase_recorded_until_silence():
    audio = make_listener()._record_phrase(FakeStream([speech()] * 3 + [quiet()] * 20))
    assert audio.dtype == np.float32
    assert 3 * FRAME <= len(audio) < 12 * FRAME


def test_silence_only_returns_none():
    assert make_listener()._record_phrase(FakeStream([quiet()] * 50)) is None


def test_single_noise_frame_is_ignored():
    stream = FakeStream([speech()] + [quiet()] * 20)
    assert make_listener()._record_phrase(stream) is None


def test_max_length_is_respected():
    audio = make_listener(max_sec=1.0)._record_phrase(FakeStream([speech()] * 200))
    assert len(audio) <= 14 * FRAME


def test_samples_are_normalized():
    audio = make_listener()._record_phrase(
        FakeStream([np.full(FRAME, 16384, dtype="int16")] * 3 + [quiet()] * 20))
    assert abs(audio.max() - 0.5) < 1e-3


# ---- wait_for_command ----
class FakeOww:
    def __init__(self):
        self.calls = 0
        self.resets = 0

    def reset(self):
        self.resets += 1

    def predict(self, frame):
        self.calls += 1
        if self.calls == 1:
            return {}                        # an empty result must not break the listener
        return {"alexa": frame[0] / 100}


def test_wait_for_command_flow():
    l = make_listener()
    l.oww = FakeOww()
    order = []
    wake_stream = FakeStream([quiet(), quiet(), quiet(), np.full(FRAME, 100, "int16")])
    phrase_stream = FakeStream([speech()] * 3 + [quiet()] * 20)
    streams = [wake_stream, phrase_stream]

    def open_stream():
        order.append("open")
        return streams.pop(0)

    l._open_stream = open_stream
    audio = l.wait_for_command(on_wake=lambda: order.append("wake"))
    assert audio is not None
    assert order == ["open", "wake", "open"]     # stream is closed during on_wake
    assert l.oww.resets == 1


# ---- constructor ----
def test_init_survives_download_failure(monkeypatch, capsys):
    monkeypatch.setattr(lst.openwakeword.utils, "download_models",
                        lambda: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(lst, "Model", lambda **k: "model")
    monkeypatch.setattr(lst.webrtcvad, "Vad", lambda level: "vad")
    l = VoiceListener(wake_model="alexa")
    assert l.oww == "model" and l.vad == "vad"
    assert "[warn]" in capsys.readouterr().out