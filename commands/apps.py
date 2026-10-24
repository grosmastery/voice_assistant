from __future__ import annotations

import os
import random
import subprocess
import threading
import webbrowser

from rapidfuzz import fuzz, process

from .games import launch_game
from .registry import with_target

MIN_SCORE = 80        # fuzzy match threshold
MIN_ALIAS_PARTIAL = 5  # use partial_ratio only for aliases at least this long


def pick_name(say: str | list[str] | None, fallback: str) -> str:
    """Spoken name from the config "say" field (a random one if it is a list)."""
    if isinstance(say, list):
        return random.choice(say) if say else fallback
    return say or fallback


def _aliases(cfg: dict) -> dict[str, tuple[str, str, object]]:
    """alias -> (kind, key, say) for all apps, games, the browser and sites."""
    out: dict[str, tuple[str, str, object]] = {}
    for key, item in cfg.get("apps", {}).items():
        for a in item.get("aliases", []):
            out[a.lower()] = ("app", key, item.get("say"))
    for key, item in cfg.get("games", {}).items():
        for a in item.get("aliases", []):
            out[a.lower()] = ("game", key, item.get("say"))
    br = cfg.get("browser", {})
    for a in br.get("aliases", []):
        out[a.lower()] = ("app", "browser", br.get("say"))
    for item in cfg.get("sites", {}).values():
        for a in item.get("aliases", []):
            out[a.lower()] = ("site", item["url"], item.get("say"))   # here the key is the URL
    return out


def find_target(rest: str, aliases: dict) -> str | None:
    # Exact -> alias as a whole word -> fuzzy -> partial (for long aliases)
    if rest in aliases:
        return rest
    words = f" {rest} "
    contained = [a for a in aliases if f" {a} " in words]
    if contained:
        return max(contained, key=len)
    match = process.extractOne(rest, list(aliases), scorer=fuzz.ratio,
                               score_cutoff=MIN_SCORE)
    if match:
        return match[0]
    long_aliases = [a for a in aliases if len(a) >= MIN_ALIAS_PARTIAL]
    match = process.extractOne(rest, long_aliases, scorer=fuzz.partial_ratio,
                               score_cutoff=90)
    return match[0] if match else None


def open_url(cfg: dict, url: str) -> None:
    exe = cfg.get("_browser_exe")
    if exe and exe.lower().endswith(".exe") and os.path.exists(exe):
        subprocess.Popen([exe, url])
    else:
        webbrowser.open(url)


def _launch_game_async(cfg: dict, key: str) -> None:
    # Launching can wait for Battle.net to start, so don't block the main loop
    def worker() -> None:
        try:
            result = launch_game(cfg, key)
            print(f"[game] {result}")
        except Exception as exc:  # noqa: BLE001
            print(f"[game] launch error: {exc}")
    threading.Thread(target=worker, daemon=True).start()


@with_target("open", "start", "launch", "run",
             "відкрий", "запусти", "включи", "відкрити", "запустити")
def open_target(cfg: dict, rest: str) -> str | None:
    aliases = _aliases(cfg)
    alias = find_target(rest, aliases)
    if alias is None:
        return None

    kind, value, say = aliases[alias]
    name = pick_name(say, alias)

    if kind == "game":
        _launch_game_async(cfg, value)
        return f"Opening {name}"

    if kind == "app":
        target = cfg.get("_resolved", {}).get(value)
        if not target:
            return f"I couldn't find {name}"
        try:
            os.startfile(target)
        except OSError:
            return f"I couldn't open {name}"
        return f"Opening {name}"

    open_url(cfg, value)
    return f"Opening {name}"