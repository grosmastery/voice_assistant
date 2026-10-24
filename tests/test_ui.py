import io
import time

import pytest
from rich.console import Console
from rich.live import Live

import ui


@pytest.fixture
def out(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(ui, "console",
                        Console(file=buf, width=100, color_system=None))
    return buf


def test_bar_levels():
    assert "█" * 8 in ui._bar(100) and "red" in ui._bar(100)
    assert "green" in ui._bar(10)
    assert "yellow" in ui._bar(60)
    assert "█" not in ui._bar(0)
    assert ui._bar(-5) == ui._bar(0)           # values are clamped to 0..100
    assert ui._bar(500) == ui._bar(100)


def test_uptime_formats(monkeypatch):
    monkeypatch.setattr(ui, "_start", time.time() - 3725)
    assert ui._uptime() == "1h 02m"
    monkeypatch.setattr(ui, "_start", time.time() - 65.3)
    assert ui._uptime() == "1m 05s"


def test_state_changes():
    ui.sleeping()
    assert ui._state == ("Sleeping", "blue")
    ui.listening()
    assert ui._state == ("Listening", "green")
    ui.thinking()
    assert ui._state == ("Recognizing", "magenta")


def test_heard_escapes_markup(out):
    ui.heard("en", "[bold]hi[/]")
    text = out.getvalue()
    assert "EN" in text and "[bold]hi[/]" in text


def test_reply_and_silence(out):
    ui.reply("Opening Steam")
    ui.reply("Oops [x]", ok=False)
    ui.silence()
    text = out.getvalue()
    assert "Opening Steam" in text and "Oops [x]" in text and "nothing heard" in text


def test_banner_uses_name(out):
    ui.banner(wake="Astra", model="whisper-small")
    text = out.getvalue()
    assert " ".join(ui.NAME.upper()) in text and "Astra" in text


def test_status_panel_content(out):
    ui.set_state("Speaking", "cyan")
    ui.console.print(ui._status())
    text = out.getvalue()
    assert "Speaking" in text and "uptime" in text and "System" in text


def test_start_live(monkeypatch):
    monkeypatch.setattr(ui, "console",
                        Console(file=io.StringIO(), width=100, force_terminal=True))
    live = ui.start_live()
    try:
        assert isinstance(live, Live)
    finally:
        live.stop()