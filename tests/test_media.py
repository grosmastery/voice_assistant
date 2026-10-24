from commands import media


def test_press_sends_down_and_up(monkeypatch):
    events = []
    monkeypatch.setattr(media.ctypes.windll.user32, "keybd_event",
                        lambda vk, scan, flags, extra: events.append((vk, flags)),
                        raising=False)
    media.press("next", times=2)
    assert events == [(0xB0, 0), (0xB0, 2)] * 2


def test_handlers_return_text(monkeypatch):
    monkeypatch.setattr(media, "press", lambda k, times=1: None)
    assert media.pause({}) == "Paused"
    assert media.play({}) == "Playing"
    assert media.mute({}) == "Muted"
    assert media.unmute({}) == "Unmuted"