import os
import subprocess
import time

from rapidfuzz import fuzz, process

from .apps import _aliases, pick_name
from .finder import resolve_exe
from .registry import with_target

NO_WINDOW = subprocess.CREATE_NO_WINDOW


def _running(image: str) -> bool:
    out = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
        capture_output=True, text=True, creationflags=NO_WINDOW,
    ).stdout
    return image.lower() in out.lower()


def _kill(image: str, force: bool):
    args = ["taskkill", "/IM", image, "/T"] + (["/F"] if force else [])
    subprocess.run(args, capture_output=True, creationflags=NO_WINDOW)


def close_processes(images, grace=3.0) -> bool:
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


def _process_names(cfg, kind, key):
    if kind == "game":
        item = cfg["games"][key]
    elif key == "browser":
        item = cfg["browser"]
    else:
        item = cfg["apps"][key]

    names = item.get("process")
    if names:
        return [names] if isinstance(names, str) else list(names)

    target = cfg.get("_resolved", {}).get(key)
    if target:
        exe = resolve_exe(target)
        if exe and exe.lower().endswith(".exe"):
            return [os.path.basename(exe)]
    return []


@with_target("close", "quit", "kill", "terminate", "закрий", "закрити")
def close_target(cfg, rest):
    aliases = _aliases(cfg)
    match = process.extractOne(rest, list(aliases), scorer=fuzz.partial_ratio,
                               score_cutoff=75)
    if not match:
        return f"Unknown app: {rest}"
    kind, value, say = aliases[match[0]]
    name = pick_name(say, match[0])
    if kind == "site":
        return "I can't close a website. Close the browser instead"

    names = _process_names(cfg, kind, value)
    if not names:
        return f"I don't know the process name for {name}"
    if close_processes(names):
        return f"Closed {name}"
    return f"{name} isn't running"