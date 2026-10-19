import os
import re
import subprocess
import winreg
import time

from .finder import resolve_exe

NO_WINDOW = subprocess.CREATE_NO_WINDOW
STEAM_KEY = r"Software\Valve\Steam"


def _is_running(image: str) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    ).stdout
    return image.lower() in out.lower()


# ---------- Battle.net ----------
def launch_battlenet_game(cfg, game_id):
    target = cfg["_resolved"].get("battlenet")
    if not target:
        return "Battle.net not found"
    exe = resolve_exe(target)
    if not exe or not os.path.exists(exe):
        os.startfile(target)         
        return "Opened Battle.net, but couldn't launch the game"
    
    cmd = f'"{exe}" --exec="launch {game_id}"'

    if _is_running("Battlenet.net.exe"):
        subprocess.Popen(cmd)
        return f"Launching {game_id}"

    subprocess.Popen(f'"{exe}"')
    deadline = time.time() + 30
    while time.time() < deadline and not _is_running("Battle.net.exe"):
        time.sleep(0.5)
    time.sleep(6)
    subprocess.Popen(cmd)
    return f"Starting Battle.net and launching {game_id}"

# ---------- Steam ----------
def _steam_dir():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STEAM_KEY) as k:
        return winreg.QueryValueEx(k, "SteamPath")[0]


def _first_steam_user(steam_dir):
    path = os.path.join(steam_dir, "config", "loginusers.vdf")
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    for _, body in re.findall(r'"(\d{17})"\s*\{(.*?)\}', text, re.S):
        name = re.search(r'"AccountName"\s+"([^"]+)"', body)
        remember = re.search(r'"RememberPassword"\s+"1"', body)
        if name and remember:
            return name.group(1)
    return None


def _set_auto_login(user):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STEAM_KEY, 0,
                        winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, "AutoLoginUser", 0, winreg.REG_SZ, user)
        winreg.SetValueEx(k, "RememberPassword", 0, winreg.REG_DWORD, 1)


def launch_steam_game(cfg, app_id):
    if not _is_running("steam.exe"):
        user = cfg.get("steam_user") or None
        try:
            user = user or _first_steam_user(_steam_dir())
            if user:
                _set_auto_login(user)
        except OSError:
            return "Steam not found"
        if not user:
            return "No saved Steam account"
    os.startfile(f"steam://rungameid/{app_id}")
    return f"Launching game {app_id}"


def launch_game(cfg, key):
    g = cfg["games"][key]
    if g["launcher"] == "battlenet":
        return launch_battlenet_game(cfg, g["game_id"])
    if g["launcher"] == "steam":
        return launch_steam_game(cfg, g["app_id"])
    return "Unknown launcher"