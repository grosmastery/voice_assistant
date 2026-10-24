from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
import winreg

from rapidfuzz import fuzz, process

START_MENU = [
    os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
]
DESKTOPS = [
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
    os.path.expandvars(r"%OneDrive%\Desktop"),
    os.path.expandvars(r"%PUBLIC%\Desktop"),
]
# Shortcuts containing these words are ignored (uninstallers)
SKIP = ("uninstall", "видалити", "удалить", "деінсталювати")
PS_UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"   # so Cyrillic names decode correctly
FUZZY_CUTOFF = 85


def _ps(command: str) -> str:
    """Run a PowerShell command and return stdout ("" on failure)."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_UTF8 + command],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return r.stdout.strip()


def _app_paths(exe: str) -> str | None:
    # Look up the exe in the registry "App Paths" key
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
            with winreg.OpenKey(root, key) as k:
                return winreg.QueryValueEx(k, None)[0]
        except OSError:
            continue
    return None


def _pick(term: str, names: list[str]) -> str | None:
    # Exact name -> shortest name containing the term -> fuzzy match
    names = [n for n in names if not any(s in n.lower() for s in SKIP)]
    low = term.lower()

    for n in names:
        if n.lower() == low:
            return n
    contains = [n for n in names if low in n.lower()]
    if contains:
        return min(contains, key=len)

    match = process.extractOne(term, names, scorer=fuzz.WRatio,
                               processor=str.lower, score_cutoff=FUZZY_CUTOFF)
    return match[0] if match else None


@functools.lru_cache(maxsize=None)
def resolve_exe(target: str) -> str:
    """Real exe path for a .lnk shortcut, other targets are returned as is."""
    if target and target.lower().endswith(".lnk"):
        p = target.replace("'", "''")   # escape quotes for PowerShell
        return _ps(f"(New-Object -ComObject WScript.Shell)"
                   f".CreateShortcut('{p}').TargetPath")
    return target


class Finder:
    def __init__(self) -> None:
        self.shortcuts = self._scan_shortcuts()      # name -> path to .lnk
        self._uwp: dict[str, str] | None = None      # name -> AppID, loaded lazily

    def _scan_shortcuts(self) -> dict[str, str]:
        found: dict[str, str] = {}
        for d in START_MENU:
            for root, _, files in os.walk(d):
                for f in files:
                    if f.lower().endswith(".lnk"):
                        found[os.path.splitext(f)[0]] = os.path.join(root, f)
        for d in DESKTOPS:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith(".lnk"):
                        found.setdefault(os.path.splitext(f)[0], os.path.join(d, f))
        return found

    def _uwp_apps(self) -> dict[str, str]:
        if self._uwp is None:
            self._uwp = {}
            try:
                out = _ps("Get-StartApps | ConvertTo-Json -Compress")
                data = json.loads(out) if out else []
                if isinstance(data, dict):
                    data = [data]
                self._uwp = {a["Name"]: a["AppID"] for a in data}
            except (ValueError, KeyError, TypeError):
                pass
        return self._uwp

    def find(self, terms: list[str], exe: str | None = None) -> str | None:
        # Search order: Start menu/desktop shortcuts, Store (UWP) apps, PATH/registry
        for term in terms:
            name = _pick(term, list(self.shortcuts))
            if name:
                return self.shortcuts[name]
        for term in terms:
            apps = self._uwp_apps()
            name = _pick(term, list(apps))
            if name:
                return "shell:AppsFolder\\" + apps[name]
        if exe:
            return shutil.which(exe) or _app_paths(exe)
        return None


def resolve_all(cfg: dict, console=None) -> None:
    """Find paths for all apps in the config once at startup.

    Result: cfg["_resolved"] (key -> path) and cfg["_browser_exe"].
    console: optional rich.Console for a colored report.
    """
    out = console.print if console else print
    finder = Finder()
    entries = dict(cfg.get("apps", {}))
    entries["browser"] = cfg.get("browser", {})
    resolved: dict[str, str | None] = {}

    for key, item in entries.items():
        manual = os.path.expandvars(item.get("path") or "")
        if manual and os.path.exists(manual):
            target: str | None = manual
        else:
            target = finder.find(item.get("find", [key]), item.get("exe"))
        resolved[key] = target
        if target:
            out(f"[green]✔[/] {key:<10} [dim]{target}[/]" if console
                else f"[ok] {key:<10} {target}")
        else:
            out(f"[red]✘[/] {key:<10} [red]not found[/]" if console
                else f"[!!] {key:<10} not found")

    cfg["_resolved"] = resolved
    browser = resolved.get("browser")
    cfg["_browser_exe"] = resolve_exe(browser) if browser else None