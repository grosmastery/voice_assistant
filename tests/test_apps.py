from commands.apps import _aliases, open_target, pick_name


def test_pick_name():
    assert pick_name("Dota 2", "dota") == "Dota 2"
    assert pick_name(None, "dota") == "dota"
    assert pick_name([], "dota") == "dota"
    assert pick_name(["A", "B"], "x") in ("A", "B")


def test_aliases_contain_all_kinds(cfg):
    a = _aliases(cfg)
    assert a["warcraft"][0] == "game"
    assert a["spotify"][0] == "app"
    assert a["opera"] == ("app", "browser", "Opera GX")
    assert a["youtube"][0] == "site"


def test_open_game_uses_say_name(cfg, monkeypatch):
    monkeypatch.setattr("commands.apps.launch_game", lambda c, k: "WoW internal")
    reply = open_target(cfg, "warcraft")
    assert reply in ("Opening Warcraft", "Opening World of Warcraft")
    assert "WoW internal" not in reply


def test_open_app_starts_resolved_path(cfg, monkeypatch):
    started = []
    monkeypatch.setattr("commands.apps.os.startfile", started.append)
    assert open_target(cfg, "spotify") == "Opening Spotify"
    assert started == [r"C:\fake\Spotify.lnk"]


def test_open_app_without_say_uses_alias(cfg, monkeypatch):
    monkeypatch.setattr("commands.apps.os.startfile", lambda p: None)
    assert open_target(cfg, "steam") == "Opening steam"


def test_open_app_not_resolved(cfg, monkeypatch):
    cfg["_resolved"]["spotify"] = None
    monkeypatch.setattr("commands.apps.os.startfile", lambda p: 1 / 0)
    assert "couldn't find" in open_target(cfg, "spotify")


def test_open_site_uses_url(cfg, monkeypatch):
    urls = []
    monkeypatch.setattr("commands.apps.open_url", lambda c, u: urls.append(u))
    open_target(cfg, "youtube")
    assert urls == ["https://www.youtube.com"]


def test_unknown_target(cfg):
    assert open_target(cfg, "zzzzzzzz").startswith("Unknown app")