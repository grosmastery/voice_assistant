import pytest

from commands import registry
from nlu.router import OK, normalize, route


@pytest.fixture
def isolated():
    saved = (list(registry.FIXED), list(registry.PREFIX), list(registry.FREEFORM))
    registry.clear()
    yield registry
    registry.clear()
    registry.FIXED.extend(saved[0])
    registry.PREFIX.extend(saved[1])
    registry.FREEFORM.extend(saved[2])


@pytest.mark.parametrize("raw, expected", [
    ("Open, Battle.net!", "open battle.net"),
    ("  Відкрий   Варкрафт. ", "відкрий варкрафт"),
    ("PAUSE the music...", "pause the music"),
    ("", ""),
    ("   ", ""),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_ok_constant():
    assert OK == "ok"


# ---- order and fallbacks (isolated registry) ----
def test_prefix_beats_freeform_and_fixed(isolated):
    isolated.with_target("zap")(lambda cfg, rest: "prefix")
    isolated.freeform(lambda cfg, t: "free")
    isolated.command("zap foo")(lambda cfg: "fixed")
    assert route("zap foo", {}) == "prefix"


def test_prefix_none_falls_to_freeform(isolated):
    isolated.with_target("zap")(lambda cfg, rest: None)
    isolated.freeform(lambda cfg, t: "free" if t.startswith("zap") else None)
    assert route("zap foo", {}) == "free"


def test_freeform_none_falls_to_fixed(isolated):
    isolated.freeform(lambda cfg, t: None)
    isolated.command("hello there")(lambda cfg: "fixed")
    assert route("hello there", {}) == "fixed"


def test_nothing_matches(isolated):
    isolated.with_target("zap")(lambda cfg, rest: None)
    isolated.command("hello there")(lambda cfg: "fixed")
    assert route("zap foo", {}) is None


def test_fixed_threshold(isolated):
    isolated.command("hello there")(lambda cfg: "fixed")
    assert route("hello ther", {}) == "fixed"
    assert route("hello ther", {}, threshold=99) is None


def test_verb_with_empty_target_is_ignored(isolated):
    isolated.with_target("zap")(lambda cfg, rest: "prefix")
    assert route("zap", {}) is None


# ---- real commands ----
def test_empty_and_noise_return_none(cfg):
    assert route("", cfg) is None
    assert route("   ", cfg) is None
    assert route("tell me a joke about cats", cfg) is None
    assert route("thanks for watching", cfg) is None


def test_open_game(cfg, monkeypatch):
    seen = []
    monkeypatch.setattr("commands.apps._launch_game_async",
                        lambda c, key: seen.append(key))
    reply = route("open Warcraft", cfg)
    assert seen == ["warcraft"]
    assert reply in ("Opening Warcraft", "Opening World of Warcraft")


def test_verb_without_space(cfg, monkeypatch):
    seen = []
    monkeypatch.setattr("commands.apps._launch_game_async",
                        lambda c, key: seen.append(key))
    route("OpenWarcraft", cfg)
    assert seen == ["warcraft"]


def test_ukrainian_verb_and_alias(cfg, monkeypatch):
    seen = []
    monkeypatch.setattr("commands.apps._launch_game_async",
                        lambda c, key: seen.append(key))
    route("відкрий варкрафт", cfg)
    assert seen == ["warcraft"]


def test_unknown_target_does_not_block_other_commands(cfg):
    assert route("run to the moon", cfg) is None
    assert route("running late", cfg) is None


def test_close_routes_to_closer(cfg, monkeypatch):
    monkeypatch.setattr("commands.closer.close_processes", lambda names: True)
    monkeypatch.setattr("commands.closer._running", lambda i: False)
    assert route("close Dota 2", cfg) == "Closed Dota 2"


@pytest.mark.parametrize("phrase, expected_press, reply", [
    ("pause the music", ("play_pause", 1), "Paused"),
    ("пауза", ("play_pause", 1), "Paused"),
    ("вимкни музику", ("play_pause", 1), "Paused"),
    ("play", ("play_pause", 1), "Playing"),
    ("resume", ("play_pause", 1), "Playing"),
    ("увімкни музику", ("play_pause", 1), "Playing"),
    ("next track", ("next", 1), "Next track"),
    ("skip", ("next", 1), "Next track"),
    ("previous track", ("prev", 1), "Previous track"),
    ("volume up", ("vol_up", 5), "Volume up"),
    ("гучніше", ("vol_up", 5), "Volume up"),
    ("volume down", ("vol_down", 5), "Volume down"),
    ("mute", ("mute", 1), "Muted"),
    ("вимкни звук", ("mute", 1), "Muted"),
    ("unmute", ("mute", 1), "Unmuted"),
    ("увімкни звук", ("mute", 1), "Unmuted"),
])
def test_media_commands(cfg, monkeypatch, phrase, expected_press, reply):
    pressed = []
    monkeypatch.setattr("commands.media.press",
                        lambda k, times=1: pressed.append((k, times)))
    assert route(phrase, cfg) == reply
    assert pressed == [expected_press]


def test_media_fuzzy_match(cfg, monkeypatch):
    pressed = []
    monkeypatch.setattr("commands.media.press",
                        lambda k, times=1: pressed.append(k))
    assert route("pause the musik", cfg) == "Paused"   # small recognition mistake
    assert pressed == ["play_pause"]