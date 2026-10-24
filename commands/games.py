from __future__ import annotations

import csv
import os
import re
import subprocess
import time
import winreg

from .finder import resolve_exe

NO_WINDOW = subprocess.CREATE_NO_WINDOW
STEAM_KEY = r"Software\Valve\Steam"
BNET_PROCESS = "Battle.net.exe"   # launcher process name in Task Manager
BNET_START_TIMEOUT = 30           # how long to wait for the process to appear, s
BNET_INIT_DELAY = 6               # delay for the launcher to initialize before launch, s


def _running_images() -> set[str]:
    """Lowercase image names of all running processes (via tasklist)."""
    out = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    ).stdout
    return {row[0].lower() for row in csv.reader(out.splitlines()) if row}


def _is_running(image: str) -> bool:
    return image.lower() in _running_images()


# ---------- Battle.net ----------
def launch_battlenet_game(cfg: dict, game_id: str) -> str:
    target = cfg.get("_resolved", {}).get("battlenet")
    if not target:
        return "Battle.net not found"
    exe = resolve_exe(target)
    if not exe or not os.path.exists(exe):
        try:
            os.startfile(target)
        except OSError:
            return "Battle.net not found"
        return "Opened Battle.net, but couldn't launch the game"

    # Battle.net only accepts --exec when the launcher is already running
    cmd = f'"{exe}" --exec="launch {game_id}"'

    if _is_running(BNET_PROCESS):
        subprocess.Popen(cmd)
        return f"Launching {game_id}"

    subprocess.Popen(f'"{exe}"')
    deadline = time.time() + BNET_START_TIMEOUT
    while time.time() < deadline and not _is_running(BNET_PROCESS):
        time.sleep(0.5)
    time.sleep(BNET_INIT_DELAY)
    subprocess.Popen(cmd)
    return f"Starting Battle.net and launching {game_id}"


# ---------- Steam ----------
def _steam_dir() -> str:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STEAM_KEY) as k:
        return winreg.QueryValueEx(k, "SteamPath")[0]


def _first_steam_user(steam_dir: str) -> str | None:
    # First account in loginusers.vdf with a remembered password
    path = os.path.join(steam_dir, "config", "loginusers.vdf")
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    for _, body in re.findall(r'"(\d{17})"\s*\{(.*?)\}', text, re.S):
        name = re.search(r'"AccountName"\s+"([^"]+)"', body)
        remember = re.search(r'"RememberPassword"\s+"1"', body)
        if name and remember:
            return name.group(1)
    return None


def _set_auto_login(user: str) -> None:
    # Makes Steam sign in to this account without asking
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STEAM_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "AutoLoginUser", 0, winreg.REG_SZ, user)
        winreg.SetValueEx(k, "RememberPassword", 0, winreg.REG_DWORD, 1)


def launch_steam_game(cfg: dict, app_id: int | str) -> str:
    if not _is_running("steam.exe"):
        user = cfg.get("steam_user") or None
        try:
            steam_dir = _steam_dir()
        except OSError:
            return "Steam not found"
        try:
            user = user or _first_steam_user(steam_dir)
        except OSError:
            return "No saved Steam account"
        if not user:
            return "No saved Steam account"
        try:
            _set_auto_login(user)
        except OSError:
            return "Couldn't set Steam auto login"
    try:
        os.startfile(f"steam://rungameid/{app_id}")
    except OSError:
        return "Couldn't launch the game through Steam"
    return f"Launching game {app_id}"


# ---------- Dispatcher ----------
def launch_game(cfg: dict, key: str) -> str:
    g = cfg.get("games", {}).get(key)
    if not g:
        return f"Unknown game: {key}"
    launcher = g.get("launcher")
    if launcher == "battlenet":
        return launch_battlenet_game(cfg, g["game_id"])
    if launcher == "steam":
        return launch_steam_game(cfg, g["app_id"])
    return "Unknown launcher"