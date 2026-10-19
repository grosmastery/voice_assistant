from commands import closer


def test_process_names_from_config(cfg):
    assert closer._process_names(cfg, "game", "warcraft") == ["Wow.exe", "WowClassic.exe"]
    assert closer._process_names(cfg, "game", "dota") == ["dota2.exe"]
    assert closer._process_names(cfg, "app", "browser") == ["opera.exe"]


def test_process_names_fallback_from_shortcut(cfg, monkeypatch):
    del cfg["apps"]["spotify"]["process"]
    monkeypatch.setattr("commands.closer.resolve_exe",
                        lambda t: r"C:\Apps\Spotify.exe")
    assert closer._process_names(cfg, "app", "spotify") == ["Spotify.exe"]


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
    assert kills == [False]                      # примусове завершення не знадобилось


def test_close_processes_forces_when_stuck(monkeypatch):
    kills = []
    monkeypatch.setattr(closer, "_running", lambda i: True)
    monkeypatch.setattr(closer, "_kill", lambda i, force: kills.append(force))
    assert closer.close_processes(["a.exe"], grace=0.4) is True
    assert kills == [False, True]


def test_close_target_messages(cfg, monkeypatch):
    monkeypatch.setattr("commands.closer.close_processes", lambda names: True)
    assert closer.close_target(cfg, "dota 2") == "Closed Dota 2"
    monkeypatch.setattr("commands.closer.close_processes", lambda names: False)
    assert closer.close_target(cfg, "dota 2") == "Dota 2 isn't running"
    assert "can't close a website" in closer.close_target(cfg, "youtube")
    assert closer.close_target(cfg, "zzzzzzzz").startswith("Unknown app")