from __future__ import annotations

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

# Media replies are only printed, not spoken (unless speak_media is on)
SILENT_REPLIES = {"Paused", "Playing", "Next track", "Previous track",
                  "Volume up", "Volume down", "Muted", "Unmuted"}


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


def main() -> None:
    cfg = load_config()
    ui.banner(wake=WAKE_NAME)
    resolve_all(cfg, ui.console)

    with ui.console.status("[cyan]Loading models...", spinner="dots"):
        stt = WhisperSTT(model_size="small", device="cpu", compute_type="int8")
        listener = VoiceListener(wake_model=WAKE_MODEL)
        speaker = build_speaker(cfg)
    ui.console.print("[bold green]✔ Ready[/]")

    def on_wake() -> None:
        ui.listening()
        if speaker:
            speaker.say("Yes?")

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
                    say("Sorry, I didn't get that", ok=False)
                elif reply == OK or (reply in SILENT_REPLIES
                                     and not cfg.get("speak_media")):
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