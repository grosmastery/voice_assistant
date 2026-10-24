import subprocess

import pytest

from commands import finder
from commands.finder import Finder, _pick


# ---- _pick ----
def test_pick_exact_match_wins():
    assert _pick("Steam", ["Steamworks Common Redistributables", "Steam"]) == "Steam"


def test_pick_prefers_shortest_containing_name():
    names = ["Opera GX Browser", "Opera GX Browser Beta", "Uninstall Opera GX"]
    assert _pick("Opera GX", names) == "Opera GX Browser"


def test_pick_fuzzy_match():
    assert _pick("Spotfy", ["Spotify", "Steam"]) == "Spotify"


def test_pick_no_match():
    assert _pick("Zzz", ["Spotify", "Steam"]) is None


def test_pick_skips_uninstallers():
    assert _pick("Steam", ["Uninstall Steam", "Видалити Steam"]) is None


# ---- PowerShell wrappers ----
def test_ps_returns_empty_on_failure(monkeypatch):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired("powershell", 30)

    monkeypatch.setattr(finder.subprocess, "run", timeout)
    assert finder._ps("x") == ""

    def missing(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr(finder.subprocess, "run", missing)
    assert finder._ps("x") == ""


def test_resolve_exe_plain_path_unchanged():
    assert finder.resolve_exe(r"C:\Apps\a.exe") == r"C:\Apps\a.exe"


def test_resolve_exe_reads_shortcut(monkeypatch):
    seen = []
    monkeypatch.setattr(finder, "_ps", lambda cmd: (seen.append(cmd), r"C:\T\t.exe")[1])
    assert finder.resolve_exe(r"C:\x\unique_test_1.lnk") == r"C:\T\t.exe"
    assert "unique_test_1.lnk" in seen[0]


# ---- Finder ----
def test_scan_shortcuts(tmp_path, monkeypatch):
    menu = tmp_path / "menu" / "sub"
    desk = tmp_path / "desk"
    menu.mkdir(parents=True)
    desk.mkdir()
    (menu / "Spotify.lnk").write_text("")
    (menu / "readme.txt").write_text("")
    (desk / "Foo.lnk").write_text("")
    (desk / "Spotify.lnk").write_text("")          # duplicate: the Start menu one wins
    monkeypatch.setattr(finder, "START_MENU", [str(tmp_path / "menu")])
    monkeypatch.setattr(finder, "DESKTOPS", [str(desk), str(tmp_path / "missing")])
    shortcuts = Finder().shortcuts
    assert set(shortcuts) == {"Spotify", "Foo"}
    assert shortcuts["Spotify"].startswith(str(tmp_path / "menu"))


def _finder(shortcuts=None, uwp=None):
    f = Finder.__new__(Finder)
    f.shortcuts = shortcuts or {}
    f._uwp = uwp if uwp is not None else {}
    return f


def test_find_prefers_shortcuts():
    f = _finder({"Spotify": r"C:\s.lnk"}, {"Spotify": "App"})
    assert f.find(["Spotify"]) == r"C:\s.lnk"


def test_find_store_app():
    f = _finder(uwp={"Telegram Desktop": "TG.App"})
    assert f.find(["Telegram"]) == "shell:AppsFolder\\TG.App"


def test_find_exe_fallback(monkeypatch):
    monkeypatch.setattr(finder.shutil, "which", lambda e: None)
    monkeypatch.setattr(finder, "_app_paths", lambda e: r"C:\reg\x.exe")
    assert _finder().find(["Nope"], exe="x.exe") == r"C:\reg\x.exe"


def test_find_nothing():
    assert _finder().find(["Nope"]) is None


# ---- resolve_all ----
class FakeFinder:
    FOUND = {"Spotify": r"C:\x\Spotify.lnk", "Opera GX": r"C:\x\Opera.lnk"}

    def find(self, terms, exe=None):
        return self.FOUND.get(terms[0])


def test_resolve_all(tmp_path, monkeypatch, capsys):
    manual = tmp_path / "steam.exe"
    manual.write_text("")
    cfg = {
        "browser": {"find": ["Opera GX"]},
        "apps": {
            "spotify": {"find": ["Spotify"]},
            "steam": {"path": str(manual), "find": ["Steam"]},
            "ghost": {"find": ["Ghost"]},
        },
    }
    monkeypatch.setattr(finder, "Finder", FakeFinder)
    monkeypatch.setattr(finder, "resolve_exe", lambda t: r"C:\Opera\opera.exe")
    finder.resolve_all(cfg)

    assert cfg["_resolved"]["spotify"] == r"C:\x\Spotify.lnk"
    assert cfg["_resolved"]["steam"] == str(manual)         # manual path takes priority
    assert cfg["_resolved"]["ghost"] is None
    assert cfg["_browser_exe"] == r"C:\Opera\opera.exe"
    out = capsys.readouterr().out
    assert "[ok] spotify" in out and "[!!] ghost" in out


def test_resolve_all_handles_empty_path_and_no_browser(monkeypatch):
    cfg = {"apps": {"x": {"path": None, "find": ["X"]}}}
    monkeypatch.setattr(finder, "Finder", FakeFinder)
    finder.resolve_all(cfg)
    assert cfg["_resolved"]["x"] is None
    assert cfg["_browser_exe"] is None


def test_resolve_all_uses_given_console(monkeypatch):
    printed = []

    class FakeConsole:
        def print(self, msg):
            printed.append(msg)

    monkeypatch.setattr(finder, "Finder", FakeFinder)
    finder.resolve_all({"apps": {"spotify": {"find": ["Spotify"]}}}, FakeConsole())
    assert any("spotify" in m for m in printed)