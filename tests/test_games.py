from types import SimpleNamespace

import pytest

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


# ---- processes ----
def test_running_images_parses_tasklist(monkeypatch):
    out = ('"Code.exe","100","Console","1","10,000 K"\r\n'
           '"Steam.exe","200","Console","1","5 K"\r\n')
    monkeypatch.setattr(games.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(stdout=out))
    assert games._running_images() == {"code.exe", "steam.exe"}


def test_is_running_exact_and_case_insensitive(monkeypatch):
    monkeypatch.setattr(games, "_running_images", lambda: {"steamwebhelper.exe", "steam.exe"})
    assert games._is_running("STEAM.EXE") is True
    monkeypatch.setattr(games, "_running_images", lambda: {"steamwebhelper.exe"})
    assert games._is_running("steam.exe") is False


# ---- Steam: loginusers.vdf ----
def test_first_steam_user_skips_unremembered(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "loginusers.vdf").write_text(VDF, encoding="utf-8")
    assert games._first_steam_user(str(tmp_path)) == "bob"


def test_first_steam_user_none(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "loginusers.vdf").write_text('"users"\n{\n}\n')
    assert games._first_steam_user(str(tmp_path)) is None


def test_first_steam_user_missing_file(tmp_path):
    with pytest.raises(OSError):
        games._first_steam_user(str(tmp_path))


# ---- Steam: launch ----
@pytest.fixture
def steam(monkeypatch):
    s = SimpleNamespace(started=[], logins=[], running=False)
    monkeypatch.setattr(games, "_is_running", lambda image: s.running)
    monkeypatch.setattr(games, "_steam_dir", lambda: r"C:\Steam")
    monkeypatch.setattr(games, "_first_steam_user", lambda d: "bob")
    monkeypatch.setattr(games, "_set_auto_login", s.logins.append)
    monkeypatch.setattr(games.os, "startfile", s.started.append, raising=False)
    return s


def test_steam_running_only_uses_url(cfg, steam):
    steam.running = True
    assert games.launch_steam_game(cfg, 570) == "Launching game 570"
    assert steam.started == ["steam://rungameid/570"]
    assert steam.logins == []                       # registry is left untouched


def test_steam_closed_sets_first_user(cfg, steam):
    games.launch_steam_game(cfg, 570)
    assert steam.logins == ["bob"]
    assert steam.started == ["steam://rungameid/570"]


def test_steam_closed_uses_configured_user(cfg, steam, monkeypatch):
    cfg["steam_user"] = "carol"
    monkeypatch.setattr(games, "_first_steam_user", lambda d: 1 / 0)
    games.launch_steam_game(cfg, 570)
    assert steam.logins == ["carol"]


def test_steam_not_installed(cfg, steam, monkeypatch):
    def missing():
        raise OSError

    monkeypatch.setattr(games, "_steam_dir", missing)
    assert games.launch_steam_game(cfg, 570) == "Steam not found"


def test_steam_no_saved_account(cfg, steam, monkeypatch):
    monkeypatch.setattr(games, "_first_steam_user", lambda d: None)
    assert games.launch_steam_game(cfg, 570) == "No saved Steam account"
    assert steam.started == []


def test_steam_url_launch_fails(cfg, steam, monkeypatch):
    def fail(url):
        raise OSError

    monkeypatch.setattr(games.os, "startfile", fail, raising=False)
    assert games.launch_steam_game(cfg, 570) == "Couldn't launch the game through Steam"


# ---- Battle.net ----
@pytest.fixture
def bnet(cfg, tmp_path, monkeypatch):
    exe = tmp_path / "Battle.net Launcher.exe"
    exe.write_text("")
    cfg["_resolved"]["battlenet"] = str(exe)
    b = SimpleNamespace(exe=str(exe), popen=[], asked=[], answers=None, cfg=cfg)

    def running(image):
        b.asked.append(image)
        return next(b.answers, True)

    monkeypatch.setattr(games, "resolve_exe", lambda t: t)
    monkeypatch.setattr(games.subprocess, "Popen", lambda cmd: b.popen.append(cmd))
    monkeypatch.setattr(games.time, "sleep", lambda s: None)
    monkeypatch.setattr(games, "_is_running", running)
    return b


def test_battlenet_already_running_single_command(bnet):
    bnet.answers = iter([True])
    games.launch_battlenet_game(bnet.cfg, "WoW")
    assert len(bnet.popen) == 1
    assert '--exec="launch WoW"' in bnet.popen[0]


def test_battlenet_checks_correct_process_name(bnet):
    bnet.answers = iter([True])
    games.launch_battlenet_game(bnet.cfg, "WoW")
    assert bnet.asked[0] == "Battle.net.exe"


def test_battlenet_closed_starts_launcher_then_game(bnet):
    bnet.answers = iter([False, True])      # not running at first, then appears
    reply = games.launch_battlenet_game(bnet.cfg, "WoW")
    assert bnet.popen[0] == f'"{bnet.exe}"'
    assert '--exec="launch WoW"' in bnet.popen[1]
    assert reply == "Starting Battle.net and launching WoW"


def test_battlenet_not_resolved(cfg):
    cfg["_resolved"]["battlenet"] = None
    assert games.launch_battlenet_game(cfg, "WoW") == "Battle.net not found"


def test_battlenet_exe_missing_opens_shortcut(cfg, monkeypatch):
    started = []
    monkeypatch.setattr(games, "resolve_exe", lambda t: r"C:\nope\x.exe")
    monkeypatch.setattr(games.os, "startfile", started.append, raising=False)
    reply = games.launch_battlenet_game(cfg, "WoW")
    assert reply == "Opened Battle.net, but couldn't launch the game"
    assert started == [r"C:\fake\Battle.net.lnk"]


def test_battlenet_exe_missing_and_startfile_fails(cfg, monkeypatch):
    def fail(p):
        raise OSError

    monkeypatch.setattr(games, "resolve_exe", lambda t: r"C:\nope\x.exe")
    monkeypatch.setattr(games.os, "startfile", fail, raising=False)
    assert games.launch_battlenet_game(cfg, "WoW") == "Battle.net not found"


# ---- dispatcher ----
def test_launch_game_dispatches_by_launcher(cfg, monkeypatch):
    calls = []
    monkeypatch.setattr(games, "launch_battlenet_game",
                        lambda c, gid: calls.append(("bnet", gid)) or "a")
    monkeypatch.setattr(games, "launch_steam_game",
                        lambda c, aid: calls.append(("steam", aid)) or "b")
    games.launch_game(cfg, "warcraft")
    games.launch_game(cfg, "dota")
    assert calls == [("bnet", "WoW"), ("steam", 570)]


def test_launch_game_unknown(cfg):
    assert games.launch_game(cfg, "nope") == "Unknown game: nope"
    cfg["games"]["odd"] = {"launcher": "epic"}
    assert games.launch_game(cfg, "odd") == "Unknown launcher"