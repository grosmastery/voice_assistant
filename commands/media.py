import ctypes
from .registry import command

KEYEVENTF_KEYUP = 0x0002
VK = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1,
      "mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF}


def press(key, times=1):
    for _ in range(times):
        ctypes.windll.user32.keybd_event(VK[key], 0, 0, 0)
        ctypes.windll.user32.keybd_event(VK[key], 0, KEYEVENTF_KEYUP, 0)


@command("pause the music", "pause", "stop the music", "play the music", "resume",
         "постав на паузу", "вимкни музику", "пауза", "увімкни музику", "продовж")
def play_pause(cfg, arg=None):
    press("play_pause")
    return "ok"


@command("next track", "next song", "skip", "наступний трек", "наступна пісня", "далі")
def next_track(cfg, arg=None):
    press("next")
    return "ok"


@command("previous track", "previous song", "попередній трек", "попередня пісня")
def prev_track(cfg, arg=None):
    press("prev")
    return "ok"


@command("volume up", "louder", "гучніше", "додай гучність")
def vol_up(cfg, arg=None):
    press("vol_up", 5) 
    return "ok"


@command("volume down", "quieter", "тихіше", "зменш гучність")
def vol_down(cfg, arg=None):
    press("vol_down", 5)
    return "ok"


@command("mute", "unmute", "вимкни звук", "увімкни звук")
def mute(cfg, arg=None):
    press("mute")
    return "ok"