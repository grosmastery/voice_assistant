from __future__ import annotations

import time
from datetime import datetime

import psutil
from rich import box
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

NAME = "Alexa"          # assistant name shown in the UI

console = Console()

_proc = psutil.Process()
_cores = psutil.cpu_count() or 1
_start = time.time()
_state: tuple[str, str] = ("Starting", "yellow")   # (label, color) for the status panel


def set_state(label: str, color: str) -> None:
    global _state
    _state = (label, color)


def _ts() -> str:
    return f"[dim]{datetime.now():%H:%M:%S}[/]"


def _bar(pct: float, width: int = 8) -> str:
    """Small colored progress bar for a percentage."""
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    color = "green" if pct < 50 else "yellow" if pct < 80 else "red"
    return f"[{color}]{'█' * filled}[/][dim]{'░' * (width - filled)}[/]"


def _uptime() -> str:
    seconds = int(time.time() - _start)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def _status() -> Panel:
    with _proc.oneshot():
        # Process CPU is summed over cores, scale it to 0-100%
        cpu = _proc.cpu_percent(None) / _cores
        mem = _proc.memory_info().rss / 1024 ** 2
    sys_cpu = psutil.cpu_percent(None)
    sys_ram = psutil.virtual_memory().percent
    label, color = _state

    body = Text.from_markup(
        f"[bold {color}]● {escape(label):<12}[/][dim]uptime {_uptime()}[/]\n"
        f"[bold]{NAME:<6}[/] CPU {_bar(cpu)} {cpu:5.1f}%   RAM {mem:5.0f} MB\n"
        f"[bold]System[/] CPU {_bar(sys_cpu)} {sys_cpu:5.1f}%   RAM {_bar(sys_ram)} {sys_ram:4.1f}%"
    )
    return Panel(body, box=box.ROUNDED, border_style="magenta",
                 title="status", title_align="left", padding=(0, 1))


def start_live() -> Live:
    # First cpu_percent(None) call always returns 0, prime the counters
    _proc.cpu_percent(None)
    psutil.cpu_percent(None)
    live = Live(get_renderable=_status, console=console,
                refresh_per_second=2, transient=False)
    live.start()
    return live


def banner(wake: str = NAME, model: str = "whisper-small") -> None:
    title = Text(" ".join(NAME.upper()), style="bold magenta", justify="center")
    sub = Text(f"wake word: {wake} · stt: {model}", style="dim", justify="center")
    console.print(Panel(Align.center(Text.assemble(title, "\n", sub)),
                        box=box.DOUBLE, border_style="cyan", padding=(0, 2)))


def sleeping(wake: str = NAME) -> None:
    set_state("Sleeping", "blue")
    console.print(f"\n{_ts()} [bold blue]💤 Sleeping[/]  [dim]say '{escape(wake)}'[/]")


def listening() -> None:
    set_state("Listening", "green")
    console.print(f"{_ts()} [bold green]🎙  Listening...[/]")


def thinking() -> None:
    set_state("Recognizing", "magenta")


def silence() -> None:
    console.print(f"{_ts()} [dim]… nothing heard[/]")


def heard(lang: str, text: str) -> None:
    console.print(f"{_ts()} [bold yellow]👂 {lang.upper()}[/] [white]{escape(text)}[/]")


def reply(text: str, ok: bool = True) -> None:
    color = "cyan" if ok else "red"
    console.print(f"{_ts()} [bold {color}]🤖 {escape(text)}[/]")