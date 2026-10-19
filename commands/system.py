from datetime import datetime 
from .registry import command

@command("what time is it", "time", "котра година", "скільки часу")
def current_time(cfg, arg=None):
    return f"It's {datetime.now().strftime('%H:%M')}"