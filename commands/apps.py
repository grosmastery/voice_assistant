import os
import subprocess
import webbrowser

from rapidfuzz import fuzz, process
from .registry import with_target
from .games import launch_game
import random

def pick_name(say, fallback):
    if isinstance(say, list):
        return random.choice(say) if say else fallback
    return say or fallback

def _aliases(cfg):
    out = {}
    for key, item in cfg.get("apps", {}).items():
        for a in item["aliases"]:
            out[a.lower()] = ("app", key, item.get("say"))
    for key, item in cfg.get("games", {}).items():
        for a in item["aliases"]:
            out[a.lower()] = ("game", key, item.get("say"))
    br = cfg.get("browser", {})
    for a in br.get("aliases", []):
        out[a.lower()] = ("app", "browser", br.get("say"))
    for item in cfg.get("sites", {}).values():
        for a in item["aliases"]:
            out[a.lower()] = ("site", item["url"], item.get("say"))
    return out


def open_url(cfg, url):
    exe = cfg.get("_browser_exe")
    if exe and exe.lower().endswith(".exe") and os.path.exists(exe):
        subprocess.Popen([exe, url])
    else:
        webbrowser.open(url)


@with_target("open", "start", "launch", "run",
             "відкрий", "запусти", "включи", "відкрити", "запустити")
def open_target(cfg, rest):
    aliases = _aliases(cfg)
    match = process.extractOne(rest, list(aliases), scorer=fuzz.partial_ratio,
                               score_cutoff=75)
    if not match:
        return f"Unknown app: {rest}"
    kind, value, say = aliases[match[0]]
    name = pick_name(say, match[0])
    if kind == "game":
        launch_game(cfg, value)
        return f"Opening {name}"
    if kind == "app":
        target = cfg["_resolved"].get(value)
        if not target:
            return f"I couldn't find {name}"
        os.startfile(target)
    else:
        open_url(cfg, value)
    return f"Opening {name}"