import json
import os
import shutil
import subprocess
import winreg

from rapidfuzz import fuzz, process
from ui import console

START_MENU = [
    os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
]
DESKTOPS = [
    os.path.expandvars(r"%USERPROFILE%\Desktop"),
    os.path.expandvars(r"%OneDrive%\Desktop"),
    os.path.expandvars(r"%PUBLIC%\Desktop"),
]
SKIP = ("uninstall", "видалити", "удалить", "деінсталювати")
PS_UTF8 = "[Console]::OutputEncoding=[Text.Encoding]::UTF8;"


def _ps(command: str) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PS_UTF8 + command],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return r.stdout.strip()


def _app_paths(exe: str):
    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe}"
            with winreg.OpenKey(root, key) as k:
                return winreg.QueryValueEx(k, None)[0]
        except OSError:
            continue
    return None


def _pick(term: str, names: list):
    names = [n for n in names if not any(s in n.lower() for s in SKIP)]
    contains = [n for n in names if term.lower() in n.lower()]
    if contains:
        return min(contains, key=len)
    match = process.extractOne(term, names, scorer=fuzz.ratio,
                               processor=str.lower, score_cutoff=80)
    return match[0] if match else None


def resolve_exe(target: str) -> str:
    if target.lower().endswith(".lnk"):
        p = target.replace("'", "''")
        return _ps(f"(New-Object -ComObject WScript.Shell)"
                   f".CreateShortcut('{p}').TargetPath")
    return target


class Finder:
    def __init__(self):
        self.shortcuts = self._scan_shortcuts()   
        self._uwp = None                          

    def _scan_shortcuts(self):
        found = {}
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

    def _uwp_apps(self):
        if self._uwp is None:
            self._uwp = {}
            try:
                out = _ps("Get-StartApps | ConvertTo-Json -Compress")
                data = json.loads(out) if out else []
                if isinstance(data, dict):
                    data = [data]
                self._uwp = {a["Name"]: a["AppID"] for a in data}
            except Exception:
                pass
        return self._uwp

    def find(self, terms, exe=None):
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


def resolve_all(cfg: dict):
    finder = Finder()
    entries = dict(cfg.get("apps", {}))
    entries["browser"] = cfg.get("browser", {})
    resolved = {}
    for key, item in entries.items():
        manual = os.path.expandvars(item.get("path", ""))
        if manual and os.path.exists(manual):
            target = manual
        else:
            target = finder.find(item.get("find", [key]), item.get("exe"))
        resolved[key] = target
        if target:
            console.print(f"[green]✔[/] {key:<10} [dim]{target}[/]")
        else:
            console.print(f"[red]✘[/] {key:<10} [red]not found[/]")
    cfg["_resolved"] = resolved

    browser = resolved.get("browser")
    cfg["_browser_exe"] = resolve_exe(browser) if browser else None