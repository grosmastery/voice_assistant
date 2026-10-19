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

console = Console()

_proc = psutil.Process()
_cores = psutil.cpu_count() or 1
_start = time.time()
_state = ("Starting", "yellow")

# перший виклик cpu_percent завжди повертає 0, тому "прогріваємо" лічильники
_proc.cpu_percent(None)
psutil.cpu_percent(None)


def set_state(label, color):
    global _state
    _state = (label, color)


def _ts():
    return f"[dim]{datetime.now():%H:%M:%S}[/]"


def _bar(pct, width=8):
    pct = max(0, min(100, pct))
    filled = round(width * pct / 100)
    color = "green" if pct < 50 else "yellow" if pct < 80 else "red"
    return f"[{color}]{'█' * filled}[/][dim]{'░' * (width - filled)}[/]"


def _status():
    with _proc.oneshot():
        cpu = _proc.cpu_percent(None) / _cores      # частка від усього процесора
        mem = _proc.memory_info().rss / 1024 ** 2
    sys_cpu = psutil.cpu_percent(None)
    sys_ram = psutil.virtual_memory().percent
    minutes = int(time.time() - _start) // 60
    h, m = divmod(minutes, 60)
    label, color = _state

    body = Text.from_markup(
        f"[bold {color}]● {label:<12}[/][dim]uptime {h}h {m:02d}m[/]\n"
        f"[bold]Alexa [/] CPU {_bar(cpu)} {cpu:5.1f}%   RAM {mem:5.0f} MB\n"
        f"[bold]System[/] CPU {_bar(sys_cpu)} {sys_cpu:5.1f}%   RAM {_bar(sys_ram)} {sys_ram:4.1f}%"
    )
    return Panel(body, box=box.ROUNDED, border_style="magenta",
                 title="status", title_align="left", padding=(0, 1))


def start_live():
    """Закріплена панель стану. Лог через console.print з'являється над нею."""
    live = Live(get_renderable=_status, console=console,
                refresh_per_second=2, transient=False)
    live.start()
    return live


def banner(wake="Alexa", model="whisper-small"):
    title = Text("A L E X A", style="bold magenta", justify="center")
    sub = Text(f"wake word: {wake} · stt: {model}", style="dim", justify="center")
    console.print(Panel(Align.center(Text.assemble(title, "\n", sub)),
                        box=box.DOUBLE, border_style="cyan", padding=(0, 2)))


def sleeping(wake="Alexa"):
    set_state("Sleeping", "blue")
    console.print(f"\n{_ts()} [bold blue]💤 Sleeping[/]  [dim]say '{wake}'[/]")


def listening():
    set_state("Listening", "green")
    console.print(f"{_ts()} [bold green]🎙  Listening...[/]")


def thinking():
    set_state("Recognizing", "magenta")


def silence():
    console.print(f"{_ts()} [dim]… nothing heard[/]")


def heard(lang, text):
    console.print(f"{_ts()} [bold yellow]👂 {lang.upper()}[/] [white]{escape(text)}[/]")


def reply(text, ok=True):
    color = "cyan" if ok else "red"
    console.print(f"{_ts()} [bold {color}]🤖 {escape(text)}[/]")