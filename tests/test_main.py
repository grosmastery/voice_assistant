import io

import numpy as np
import pytest
import yaml
from rich.console import Console

import main as app
from nlu.router import OK

VOICE = np.full(16000, 0.5, dtype="float32")
QUIET = np.zeros(16000, dtype="float32")


class FakeListener:
    def __init__(self, items):
        self.items = list(items)

    def wait_for_command(self, on_wake=None):
        if not self.items:
            raise KeyboardInterrupt
        if on_wake:
            on_wake()
        return self.items.pop(0)


class FakeSTT:
    description = "fake"

    def __init__(self, results):
        self.results = list(results)

    def transcribe(self, audio):
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class FakeSpeaker:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)


class FakeLive:
    stopped = False

    def stop(self):
        FakeLive.stopped = True


LOGGED = []


def run(monkeypatch, cfg, audios, stt_results, route_fn):
    speaker = FakeSpeaker()
    monkeypatch.setattr(app, "load_config", lambda *a: cfg)
    monkeypatch.setattr(app, "resolve_all", lambda *a, **k: None)
    monkeypatch.setattr(app, "WhisperSTT", lambda **k: FakeSTT(stt_results))
    monkeypatch.setattr(app, "VoiceListener", lambda **k: FakeListener(audios))
    monkeypatch.setattr(app, "build_speaker", lambda c: speaker)
    monkeypatch.setattr(app, "beep", lambda: speaker.spoken.append("<beep>"))
    monkeypatch.setattr(app, "log_unrecognized", lambda text, lang: LOGGED.append((text, lang)))
    monkeypatch.setattr(app, "route", route_fn)
    monkeypatch.setattr(app.ui, "start_live", lambda: FakeLive())
    monkeypatch.setattr(app.ui, "console", Console(file=io.StringIO(), width=100))
    app.main()
    return speaker.spoken


# ---- load_config / build_speaker ----
def test_load_config(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("steam_user: 'x'\napps: {}\n", encoding="utf-8")
    assert app.load_config(str(p)) == {"steam_user": "x", "apps": {}}


def test_build_speaker_disabled():
    assert app.build_speaker({"tts": {"enabled": False}}) is None
    assert app.build_speaker({}) is None


def test_build_speaker_without_voice(monkeypatch):
    monkeypatch.setattr(app.ui, "console", Console(file=io.StringIO()))
    assert app.build_speaker({"tts": {"enabled": True, "voices": {}}}) is None


def test_build_speaker_ok(monkeypatch):
    warmed = []

    class S:
        def __init__(self, path):
            self.path = path

        def warm_up(self, phrases):
            warmed.extend(phrases)

    monkeypatch.setattr(app, "Speaker", S)
    s = app.build_speaker({"tts": {"enabled": True, "voices": {"en": "v.onnx"}}})
    assert s.path == "v.onnx" and "Yes?" in warmed


def test_build_stt_defaults_and_config(monkeypatch):
    monkeypatch.setattr(app, "WhisperSTT", lambda **k: k)
    assert app.build_stt({}) == {
        "model_size": "large-v3-turbo", "device": "auto", "compute_type": "float16",
        "cpu_model": "small", "beam_size": 5, "vad_filter": False,
    }
    k = app.build_stt({"stt": {"device": "cpu", "cpu_model": "base", "beam_size": 1}})
    assert k["device"] == "cpu" and k["cpu_model"] == "base" and k["beam_size"] == 1


# ---- main loop ----
def test_reply_is_spoken(monkeypatch):
    spoken = run(monkeypatch, {}, [VOICE], [("open steam", "en")],
                 lambda t, c: "Opening Steam")
    assert spoken == ["<beep>", "Opening Steam"]
    assert FakeLive.stopped


def test_unknown_command_apology(monkeypatch):
    LOGGED.clear()
    spoken = run(monkeypatch, {}, [VOICE], [("blah", "en")], lambda t, c: None)
    assert spoken == ["<beep>", "Sorry, I didn't get that"]
    assert LOGGED == [("blah", "en")]


def test_known_command_is_not_logged(monkeypatch):
    LOGGED.clear()
    run(monkeypatch, {}, [VOICE], [("open steam", "en")], lambda t, c: "Opening Steam")
    assert LOGGED == []


def test_dictation_reply_is_not_spoken(monkeypatch):
    spoken = run(monkeypatch, {}, [VOICE], [("type hi", "en")], lambda t, c: "Typed: Hi")
    assert spoken == ["<beep>"]


def test_log_unrecognized_appends(tmp_path):
    path = tmp_path / "logs" / "unrecognized.log"
    app.log_unrecognized("open stim", "en", str(path))
    app.log_unrecognized("відкрий щось", "uk", str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0].endswith("	en	open stim") and lines[1].endswith("	uk	відкрий щось")


def test_log_unrecognized_never_raises(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    app.log_unrecognized("x", "en", str(blocker / "sub" / "log.txt"))   # dir is a file


def test_ok_reply_is_not_spoken(monkeypatch):
    spoken = run(monkeypatch, {}, [VOICE], [("x", "en")], lambda t, c: OK)
    assert spoken == ["<beep>"]


def test_quiet_or_missing_audio_skips_stt(monkeypatch):
    # if STT were called, FakeSTT with no results would raise IndexError
    spoken = run(monkeypatch, {}, [QUIET, None], [], lambda t, c: "never")
    assert spoken == ["<beep>", "<beep>"]


def test_empty_text_skips_routing(monkeypatch):
    calls = []
    run(monkeypatch, {}, [VOICE], [("", "en")],
        lambda t, c: calls.append(t) or "x")
    assert calls == []


def test_error_does_not_stop_loop(monkeypatch):
    spoken = run(monkeypatch, {}, [VOICE, VOICE],
                 [RuntimeError("boom"), ("hello", "en")], lambda t, c: "Done")
    assert spoken[-1] == "Done"


# Media replies (SILENT_REPLIES) are printed only, unless cfg["speak_media"] is on
def test_media_reply_silent_by_default(monkeypatch):
    spoken = run(monkeypatch, {}, [VOICE], [("pause", "en")], lambda t, c: "Paused")
    assert spoken == ["<beep>"]


def test_media_reply_spoken_when_enabled(monkeypatch):
    spoken = run(monkeypatch, {"speak_media": True}, [VOICE], [("pause", "en")],
                 lambda t, c: "Paused")
    assert spoken == ["<beep>", "Paused"]


# ---- wake reply ----
def test_wake_reply_voice(monkeypatch):
    spoken = run(monkeypatch, {"wake_reply": "voice"}, [VOICE], [("x", "en")],
                 lambda t, c: OK)
    assert spoken == ["Yes?"]


def test_wake_reply_none(monkeypatch):
    spoken = run(monkeypatch, {"wake_reply": "none"}, [VOICE], [("x", "en")],
                 lambda t, c: OK)
    assert spoken == []
