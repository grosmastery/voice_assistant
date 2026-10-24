from __future__ import annotations

import ctypes
from ctypes import wintypes

from .registry import with_target

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004   # send a character itself, works with any keyboard layout


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    # Not used, but it is the biggest union member, so INPUT gets the right size
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send(inputs: list[INPUT]) -> int:
    arr = (INPUT * len(inputs))(*inputs)
    return ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def type_text(text: str) -> int:
    """Type text into the focused window. Returns how many key events were sent."""
    data = text.encode("utf-16-le")
    inputs = []
    # One UTF-16 code unit per event, so emoji/rare chars go as surrogate pairs
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inputs.append(INPUT(type=INPUT_KEYBOARD,
                                u=_INPUTUNION(ki=KEYBDINPUT(0, unit, flags, 0, 0))))
    return _send(inputs) if inputs else 0


@with_target("type", "dictate", "write", "надрукуй", "напиши", "введи", raw=True)
def dictate(cfg: dict, rest: str) -> str | None:
    text = rest[:1].upper() + rest[1:]
    if not type_text(text):
        return "I couldn't type that"   # e.g. the focused window runs as admin
    return f"Typed: {text}"
