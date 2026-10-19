import time

from commands import games

VDF = '''"users"
{
    "76561198000000001"
    {
        "AccountName"        "alice"
        "RememberPassword"   "0"
    }
    "76561198000000002"
    {
        "AccountName"        "bob"
        "RememberPassword"   "1"
    }
}
'''


def test_first_steam_user_skips_unremembered(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "loginusers.vdf").write_text(VDF, encoding="utf-8")
    assert games._first_steam_user(str(tmp_path)) == "bob"


def test_first_steam_user_none(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "loginusers.vdf").write_text('"users"\n{\n}\n')
    assert games._first_steam_user(str(tmp_path)) is None


def _patch_bnet(monkeypatch, running):
    popen = []
    monkeypatch.setattr(games, "resolve_exe", lambda t: r"C:\bnet\Battle.net Launcher.exe")
    monkeypatch.setattr(games.os.path, "exists", lambda p: True)
    monkeypatch.setattr(games.subprocess, "Popen", lambda cmd: popen.append(cmd))
    monkeypatch.setattr(time, "sleep", lambda s: None)
    monkeypatch.setattr(games, "_is_running", running)
    return popen


def test_battlenet_already_running_single_command(cfg, monkeypatch):
    popen = _patch_bnet(monkeypatch, lambda image: True)
    games.launch_battlenet_game(cfg, "WoW")
    assert len(popen) == 1
    assert '--exec="launch WoW"' in popen[0]


def test_battlenet_closed_starts_launcher_then_game(cfg, monkeypatch):
    answers = iter([False, True, True, True])
    popen = _patch_bnet(monkeypatch, lambda image: next(answers, True))
    games.launch_battlenet_game(cfg, "WoW")
    assert len(popen) == 2
    assert "--exec" not in popen[0]
    assert '--exec="launch WoW"' in popen[1]


def test_battlenet_not_found(cfg):
    cfg["_resolved"]["battlenet"] = None
    assert games.launch_battlenet_game(cfg, "WoW") == "Battle.net not found"


def test_steam_game_uses_url_when_steam_running(cfg, monkeypatch):
    started = []
    monkeypatch.setattr(games, "_is_running", lambda image: True)
    monkeypatch.setattr(games.os, "startfile", started.append)
    games.launch_steam_game(cfg, 570)
    assert started == ["steam://rungameid/570"]


def test_launch_game_dispatches_by_launcher(cfg, monkeypatch):
    calls = []
    monkeypatch.setattr(games, "launch_battlenet_game",
                        lambda c, gid: calls.append(("bnet", gid)))
    monkeypatch.setattr(games, "launch_steam_game",
                        lambda c, aid: calls.append(("steam", aid)))
    games.launch_game(cfg, "warcraft")
    games.launch_game(cfg, "dota")
    assert calls == [("bnet", "WoW"), ("steam", 570)]