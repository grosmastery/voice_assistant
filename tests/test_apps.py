import threading

from commands import apps
from commands.apps import (_aliases, _launch_game_async, find_target, open_target,
                           open_url, pick_name)


def test_pick_name():
    assert pick_name("Dota 2", "dota") == "Dota 2"
    assert pick_name(None, "dota") == "dota"
    assert pick_name("", "dota") == "dota"
    assert pick_name([], "dota") == "dota"
    assert pick_name(["A", "B"], "x") in ("A", "B")


def test_aliases_contain_all_kinds(cfg):
    a = _aliases(cfg)
    assert a["warcraft"] == ("game", "warcraft", ["Warcraft", "World of Warcraft"])
    assert a["spotify"] == ("app", "spotify", "Spotify")
    assert a["opera"] == ("app", "browser", "Opera GX")
    assert a["youtube"] == ("site", "https://www.youtube.com", None)   # for a site the key is the URL


def test_aliases_tolerate_missing_fields():
    assert _aliases({"apps": {"x": {}}, "games": {"y": {}}, "sites": {}}) == {}


# ---- find_target ----
def test_find_target_exact(cfg):
    assert find_target("steam", _aliases(cfg)) == "steam"


def test_find_target_word_inside_phrase(cfg):
    assert find_target("steam please", _aliases(cfg)) == "steam"


def test_find_target_prefers_longest_contained(cfg):
    assert find_target("open dota 2 now", _aliases(cfg)) == "dota 2"


def test_find_target_fuzzy(cfg):
    assert find_target("spotfy", _aliases(cfg)) == "spotify"


def test_find_target_no_match(cfg):
    a = _aliases(cfg)
    assert find_target("zzzzzzzz", a) is None
    assert find_target("the stream is great", a) is None   # short words don't match


# ---- open_target ----
def test_open_game_uses_say_name_and_async(cfg, monkeypatch):
    called = []
    monkeypatch.setattr(apps, "_launch_game_async", lambda c, k: called.append(k))
    reply = open_target(cfg, "warcraft")
    assert called == ["warcraft"]
    assert reply in ("Opening Warcraft", "Opening World of Warcraft")


def test_open_app_starts_resolved_path(cfg, monkeypatch):
    started = []
    monkeypatch.setattr(apps.os, "startfile", started.append, raising=False)
    assert open_target(cfg, "spotify") == "Opening Spotify"
    assert started == [r"C:\fake\Spotify.lnk"]


def test_open_app_not_resolved(cfg, monkeypatch):
    cfg["_resolved"]["spotify"] = None
    monkeypatch.setattr(apps.os, "startfile", lambda p: 1 / 0, raising=False)
    assert open_target(cfg, "spotify") == "I couldn't find Spotify"


def test_open_app_startfile_fails(cfg, monkeypatch):
    def fail(path):
        raise OSError("nope")

    monkeypatch.setattr(apps.os, "startfile", fail, raising=False)
    assert open_target(cfg, "spotify") == "I couldn't open Spotify"


def test_open_site(cfg, monkeypatch):
    urls = []
    monkeypatch.setattr(apps, "open_url", lambda c, u: urls.append(u))
    assert open_target(cfg, "youtube") == "Opening youtube"
    assert urls == ["https://www.youtube.com"]


def test_unknown_target_returns_none(cfg):
    assert open_target(cfg, "zzzzzzzz") is None
    assert open_target(cfg, "the stream is great") is None


# ---- open_url ----
def test_open_url_uses_browser_exe(cfg, tmp_path, monkeypatch):
    exe = tmp_path / "opera.exe"
    exe.write_text("")
    cfg["_browser_exe"] = str(exe)
    popen = []
    monkeypatch.setattr(apps.subprocess, "Popen", lambda args: popen.append(args))
    open_url(cfg, "https://x.y")
    assert popen == [[str(exe), "https://x.y"]]


def test_open_url_falls_back_to_default_browser(cfg, monkeypatch):
    opened = []
    monkeypatch.setattr(apps.webbrowser, "open", opened.append)
    open_url(cfg, "https://x.y")
    assert opened == ["https://x.y"]


# ---- game launch thread ----
def test_launch_game_async_runs_in_thread(cfg, monkeypatch):
    done = threading.Event()
    names = []

    def fake_launch(c, key):
        names.append(threading.current_thread().name)
        done.set()
        return "ok"

    monkeypatch.setattr(apps, "launch_game", fake_launch)
    _launch_game_async(cfg, "warcraft")
    assert done.wait(2)
    assert names[0] != threading.main_thread().name


def test_launch_game_async_swallows_errors(cfg, monkeypatch, capsys):
    done = threading.Event()

    def boom(c, key):
        done.set()
        raise RuntimeError("fail")

    monkeypatch.setattr(apps, "launch_game", boom)
    _launch_game_async(cfg, "warcraft")
    assert done.wait(2)
    threading.Event().wait(0.2)      # give the thread time to print the error
    assert "[game]" in capsys.readouterr().out