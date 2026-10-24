from __future__ import annotations

import os
import winsound
from datetime import datetime

import numpy as np
import yaml

import commands  # noqa: F401  (registers commands via decorators)
import ui
from audio.listener import VoiceListener
from commands.finder import resolve_all
from nlu.router import OK, route
from stt.whisper_engine import WhisperSTT
from tts.piper_tts import Speaker

WAKE_MODEL = "alexa"
WAKE_NAME = "Alexa"       # name shown in the UI
MIN_PEAK = 0.02           # recordings quieter than this count as silence
UNRECOGNIZED_LOG = os.path.join("logs", "unrecognized.log")

# Media replies are only printed, not spoken (unless speak_media is on)
SILENT_REPLIES = {"Paused", "Playing", "Next track", "Previous track",
                  "Volume up", "Volume down", "Muted", "Unmuted"}
# Replies with these prefixes are never spoken (dictation would read the text back)
CONSOLE_ONLY = ("Typed: ",)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_speaker(cfg: dict) -> Speaker | None:
    tts_cfg = cfg.get("tts", {})
    if not tts_cfg.get("enabled"):
        return None
    voice = tts_cfg.get("voices", {}).get("en")
    if not voice:
        ui.console.print("[red]tts.voices.en is not set in config.yaml, voice disabled[/]")
        return None
    speaker = Speaker(voice)
    # Pre-render common phrases so the first reply has no delay
    speaker.warm_up(["Yes?", "Sorry, I didn't get that"])
    return speaker


def build_stt(cfg: dict) -> WhisperSTT:
    s = cfg.get("stt", {})
    return WhisperSTT(
        model_size=s.get("model", "large-v3-turbo"),
        device=s.get("device", "auto"),
        compute_type=s.get("compute_type", "float16"),
        cpu_model=s.get("cpu_model", "small"),
        beam_size=s.get("beam_size", 5),
        vad_filter=s.get("vad_filter", False),
    )


def log_unrecognized(text: str, lang: str, path: str | None = None) -> None:
    """Append a phrase no command matched, to find missing aliases later."""
    path = path or UNRECOGNIZED_LOG
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{lang}\t{text}\n")
    except OSError:
        pass   # logging must never break the assistant


def beep() -> None:
    winsound.Beep(880, 80)   # blocks only 80 ms, unlike a spoken "Yes?"


def main() -> None:
    cfg = load_config()
    ui.banner(wake=WAKE_NAME, model=cfg.get("stt", {}).get("model", "large-v3-turbo"))
    resolve_all(cfg, ui.console)

    with ui.console.status("[cyan]Loading models...", spinner="dots"):
        stt = build_stt(cfg)
        listener = VoiceListener(wake_model=WAKE_MODEL)
        speaker = build_speaker(cfg)
    ui.console.print(f"[bold green]✔ Ready[/] [dim]stt: {stt.description}[/]")

    def on_wake() -> None:
        ui.listening()
        # wake_reply: "beep" (default, fastest), "voice" (says "Yes?") or "none"
        mode = cfg.get("wake_reply", "beep")
        if mode == "voice" and speaker:
            speaker.say("Yes?")
        elif mode == "beep":
            beep()

    def say(text: str, ok: bool = True) -> None:
        ui.reply(text, ok)
        if speaker and text:
            ui.set_state("Speaking", "cyan")
            speaker.say(text)

    live = ui.start_live()
    try:
        # Main loop: wake word -> record -> STT -> route -> reply
        while True:
            try:
                ui.sleeping(WAKE_NAME)
                audio = listener.wait_for_command(on_wake=on_wake)
                if audio is None or np.abs(audio).max() < MIN_PEAK:
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
                    log_unrecognized(text, lang)
                    say("Sorry, I didn't get that", ok=False)
                elif (reply == OK or reply.startswith(CONSOLE_ONLY)
                      or (reply in SILENT_REPLIES and not cfg.get("speak_media"))):
                    ui.reply(reply)          # console only
                else:
                    say(reply)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001  keep running after any error
                ui.reply(f"Error: {exc}", ok=False)
    except KeyboardInterrupt:
        ui.console.print("\n[dim]Bye.[/]")
    finally:
        live.stop()


if __name__ == "__main__":
    main()