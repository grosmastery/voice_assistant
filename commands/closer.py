from __future__ import annotations

import os
import subprocess
import time

from .apps import _aliases, find_target, pick_name
from .finder import resolve_exe
from .registry import with_target
from .games import _running_images

NO_WINDOW = subprocess.CREATE_NO_WINDOW
GRACE_SEC = 3.0   # how long to wait for a graceful close before force-killing


def _running(image: str) -> bool:
    return image.lower() in _running_images()


def _kill(image: str, force: bool) -> None:
    args = ["taskkill", "/IM", image, "/T"] + (["/F"] if force else [])
    subprocess.run(args, capture_output=True, creationflags=NO_WINDOW)


def close_processes(images: list[str], grace: float = GRACE_SEC) -> bool:
    """Ask processes to close, force-kill leftovers. False if none were running."""
    running = [i for i in images if _running(i)]
    if not running:
        return False

    for i in running:
        _kill(i, force=False)

    deadline = time.time() + grace
    while time.time() < deadline and any(_running(i) for i in running):
        time.sleep(0.3)

    for i in running:
        if _running(i):
            _kill(i, force=True)
    return True


def _entry(cfg: dict, kind: str, key: str) -> dict:
    if kind == "game":
        return cfg.get("games", {}).get(key, {})
    if key == "browser":
        return cfg.get("browser", {})
    return cfg.get("apps", {}).get(key, {})


def _process_names(cfg: dict, kind: str, key: str) -> list[str]:
    # Explicit "process" in the config wins, otherwise take the exe name from the resolved path
    names = _entry(cfg, kind, key).get("process")
    if names:
        return [names] if isinstance(names, str) else list(names)

    target = cfg.get("_resolved", {}).get(key)
    if target:
        exe = resolve_exe(target)
        if exe and exe.lower().endswith(".exe"):
            return [os.path.basename(exe)]
    return []


@with_target("close", "quit", "kill", "terminate", "закрий", "закрити")
def close_target(cfg: dict, rest: str) -> str | None:
    aliases = _aliases(cfg)
    alias = find_target(rest, aliases)
    if alias is None:
        return None

    kind, value, say = aliases[alias]
    name = pick_name(say, alias)
    if kind == "site":
        return "I can't close a website. Close the browser instead"

    names = _process_names(cfg, kind, value)
    if not names:
        return f"I don't know the process name for {name}"
    if not close_processes(names):
        return f"{name} isn't running"
    if any(_running(i) for i in names):       # e.g. no admin rights
        return f"I couldn't close {name}"
    return f"Closed {name}"