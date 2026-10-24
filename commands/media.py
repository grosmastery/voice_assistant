from __future__ import annotations

import ctypes

from .registry import command

KEYEVENTF_KEYUP = 0x0002
# Windows virtual-key codes for media keys
VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1,
      "mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF}
VOLUME_STEPS = 5   # one step = 2%


def press(key: str, times: int = 1) -> None:
    """Simulate a media key press (down + up)."""
    for _ in range(times):
        ctypes.windll.user32.keybd_event(VK[key], 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK[key], 0, KEYEVENTF_KEYUP, 0)


@command("pause the music", "pause", "stop the music", "stop",
         "постав на паузу", "пауза", "вимкни музику", "зупини музику")
def pause(cfg, arg=None):
    press("play_pause")
    return "Paused"


@command("play the music", "play", "resume", "continue",
         "увімкни музику", "продовж", "грай")
def play(cfg, arg=None):
    press("play_pause")
    return "Playing"


@command("next track", "next song", "skip", "next",
         "наступний трек", "наступна пісня", "далі")
def next_track(cfg, arg=None):
    press("next")
    return "Next track"


@command("previous track", "previous song", "go back",
         "попередній трек", "попередня пісня")
def prev_track(cfg, arg=None):
    press("prev")
    return "Previous track"


@command("volume up", "louder", "гучніше", "додай гучність")
def vol_up(cfg, arg=None):
    press("vol_up", VOLUME_STEPS)
    return "Volume up"


@command("volume down", "quieter", "тихіше", "зменш гучність")
def vol_down(cfg, arg=None):
    press("vol_down", VOLUME_STEPS)
    return "Volume down"


@command("mute", "вимкни звук")
def mute(cfg, arg=None):
    press("mute")
    return "Muted"


@command("unmute", "увімкни звук")
def unmute(cfg, arg=None):
    # Same key as mute, it toggles
    press("mute")
    return "Unmuted"