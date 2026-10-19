import numpy as np
import yaml

import commands  # noqa: F401
import ui
from audio.listener import VoiceListener
from commands.finder import resolve_all
from nlu.router import route
from stt.whisper_engine import WhisperSTT
from tts.piper_tts import Speaker

WAKE = "alexa"


with open("config.yaml", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

ui.banner(wake=WAKE.capitalize())
resolve_all(cfg)

with ui.console.status("[cyan]Loading models...", spinner="dots"):
    stt = WhisperSTT(model_size="small", device="cpu", compute_type="int8")
    listener = VoiceListener(wake_model=WAKE)
    tts_cfg = cfg.get("tts", {})
    speaker = Speaker(tts_cfg["voices"]["en"]) if tts_cfg.get("enabled") else None
ui.console.print("[bold green]✔ Ready[/]")

def on_wake():
    ui.listening()
    if speaker:
        speaker.say("Yes?")

def say(text, ok=True):
    ui.reply(text, ok)
    if speaker and text:
        ui.set_state("Speaking", "cyan")
        speaker.say(text)

live = ui.start_live() 
try:
    while True:
        ui.sleeping(WAKE.capitalize())
        audio = listener.wait_for_command(on_wake=on_wake)
        if audio is None or np.abs(audio).max() < 0.02:
            ui.silence()
            continue

        ui.thinking()
        text, lang = stt.transcribe(audio)
        if not text:
            ui.silence()
            continue
        ui.heard(lang, text)

        reply = route(text, cfg)
        if reply is None:
            say("Sorry, I didn't get that", ok=False)
        elif reply == "ok":
            ui.reply("ok")
        else:
            say(reply)
except KeyboardInterrupt:
    ui.console.print("\n[dim]Bye.[/]")
finally:
    live.stop()