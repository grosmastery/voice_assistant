import pytest

from nlu.router import normalize, route


@pytest.mark.parametrize("raw, expected", [
    ("Open, Battle.net!", "open battle.net"),
    ("  Відкрий   Варкрафт. ", "відкрий варкрафт"),
    ("PAUSE the music...", "pause the music"),
    ("", ""),
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


def test_empty_and_noise_return_none(cfg):
    assert route("", cfg) is None
    assert route("tell me a joke about cats", cfg) is None
    assert route("thanks for watching", cfg) is None


def test_prefix_command_gets_target(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr("commands.apps.launch_game",
                        lambda c, key: seen.setdefault("game", key))
    reply = route("open Warcraft", cfg)
    assert seen["game"] == "warcraft"
    assert reply.startswith("Opening")


def test_verb_without_space(cfg, monkeypatch):
    """Whisper інколи склеює слова: 'OpenWarcraft'."""
    seen = {}
    monkeypatch.setattr("commands.apps.launch_game",
                        lambda c, key: seen.setdefault("game", key))
    route("OpenWarcraft", cfg)
    assert seen["game"] == "warcraft"


def test_ukrainian_verb_and_alias(cfg, monkeypatch):
    seen = {}
    monkeypatch.setattr("commands.apps.launch_game",
                        lambda c, key: seen.setdefault("game", key))
    route("відкрий варкрафт", cfg)
    assert seen["game"] == "warcraft"


def test_fixed_command_fuzzy(cfg, monkeypatch):
    pressed = []
    monkeypatch.setattr("commands.media.press", lambda k, times=1: pressed.append(k))
    assert route("pause the music", cfg) == "ok"
    assert route("pause the musik", cfg) == "ok"      # дрібна помилка розпізнавання
    assert pressed == ["play_pause", "play_pause"]


@pytest.mark.parametrize("phrase, key", [
    ("next track", "next"), ("volume down", "vol_down"),
    ("гучніше", "vol_up"), ("пауза", "play_pause"),
])
def test_media_commands(cfg, monkeypatch, phrase, key):
    pressed = []
    monkeypatch.setattr("commands.media.press", lambda k, times=1: pressed.append(k))
    assert route(phrase, cfg) == "ok"
    assert pressed == [key]


def test_time_command(cfg):
    reply = route("what time is it", cfg)
    assert reply and ":" in reply


def test_music_phrase_is_not_taken_as_open_command(cfg, monkeypatch):
    """'вимкни музику' не має ставати помилкою 'Unknown app'."""
    monkeypatch.setattr("commands.media.press", lambda k, times=1: None)
    assert route("вимкни музику", cfg) == "ok"