import pytest

from commands import closer


def test_running_is_exact_match(monkeypatch):
    monkeypatch.setattr(closer, "_running_images",
                        lambda: {"steamwebhelper.exe", "code.exe"})
    assert closer._running("steam.exe") is False
    assert closer._running("Code.exe") is True


def test_process_names_from_config(cfg):
    assert closer._process_names(cfg, "game", "warcraft") == ["Wow.exe"]
    assert closer._process_names(cfg, "game", "dota") == ["dota2.exe"]
    assert closer._process_names(cfg, "app", "browser") == ["opera.exe"]


def test_process_names_fallback_from_shortcut(cfg, monkeypatch):
    del cfg["apps"]["spotify"]["process"]
    monkeypatch.setattr(closer, "resolve_exe", lambda t: r"C:\Apps\Spotify.exe")
    assert closer._process_names(cfg, "app", "spotify") == ["Spotify.exe"]


def test_process_names_unknown(cfg):
    assert closer._process_names(cfg, "game", "nope") == []


def test_close_processes_not_running(monkeypatch):
    monkeypatch.setattr(closer, "_running", lambda i: False)
    monkeypatch.setattr(closer, "_kill", lambda i, force: 1 / 0)
    assert closer.close_processes(["a.exe"]) is False


def test_close_processes_soft_close_is_enough(monkeypatch):
    state = {"alive": True}
    kills = []

    def kill(image, force):
        kills.append(force)
        state["alive"] = False

    monkeypatch.setattr(closer, "_running", lambda i: state["alive"])
    monkeypatch.setattr(closer, "_kill", kill)
    assert closer.close_processes(["a.exe"], grace=1) is True
    assert kills == [False]


def test_close_processes_forces_when_stuck(monkeypatch):
    kills = []
    monkeypatch.setattr(closer, "_running", lambda i: True)
    monkeypatch.setattr(closer, "_kill", lambda i, force: kills.append(force))
    assert closer.close_processes(["a.exe"], grace=0.35) is True
    assert kills == [False, True]


@pytest.mark.parametrize("closed, still_running, expected", [
    (True, False, "Closed Dota 2"),
    (False, False, "Dota 2 isn't running"),
    (True, True, "I couldn't close Dota 2"),
])
def test_close_target_messages(cfg, monkeypatch, closed, still_running, expected):
    monkeypatch.setattr(closer, "close_processes", lambda names: closed)
    monkeypatch.setattr(closer, "_running", lambda i: still_running)
    assert closer.close_target(cfg, "dota 2") == expected


def test_close_site_is_refused(cfg):
    assert closer.close_target(cfg, "youtube") == \
        "I can't close a website. Close the browser instead"


def test_close_unknown_returns_none(cfg):
    assert closer.close_target(cfg, "zzzzzzzz") is None


def test_close_without_process_name(cfg):
    del cfg["apps"]["steam"]["process"]
    cfg["_resolved"]["steam"] = None
    assert closer.close_target(cfg, "steam") == "I don't know the process name for Steam"