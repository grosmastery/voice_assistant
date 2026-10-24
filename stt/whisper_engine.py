from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

# Language detection is limited to these; PRIORITY can bias one of them
ALLOWED: tuple[str, ...] = ("en", "uk")
PRIORITY: dict[str, float] = {"en": 1.0, "uk": 1.0}
DEFAULT_LANG = "en"

# Names added to the prompt so Whisper spells them correctly
APPS: list[str] = [
    "Warcraft", "Battle.net", "Opera GX", "Spotify",
    "Steam", "Dota 2", "Hearthstone", "VS Code",
]

# Typical Whisper hallucinations on silence/noise, such results are dropped
HALLUCINATIONS: tuple[str, ...] = (
    "thanks for watching", "thank you for watching", "see you in the next",
    "subscribe", "subtitles by", "дякую за перегляд", "підписуйтесь",
    "продовження слідує", "субтитри",
)

MIN_SAMPLES = 1600   # 0.1 s at 16 kHz, shorter audio is skipped


class WhisperSTT:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        app_names: list[str] | None = None,
    ) -> None:
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        names = app_names if app_names else APPS
        self.prompt: str = (
            "Open Warcraft. Відкрий Warcraft. Start Battle.net. "
            "Запусти Battle.net. Pause the music. Постав музику на паузу. "
            "Close Steam. Quit Spotify. Close Dota 2. Закрий Steam. "
            + " ".join(names)
        )

    def _pick_language(self, audio: np.ndarray) -> str:
        _, _, probs = self.model.detect_language(audio)
        scores = {
            lang: p * PRIORITY.get(lang, 1.0)
            for lang, p in probs
            if lang in ALLOWED
        }
        if not scores:
            return DEFAULT_LANG
        return max(scores, key=scores.get)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        if audio is None or audio.size < MIN_SAMPLES:
            return "", DEFAULT_LANG

        lang = self._pick_language(audio)
        segments, _ = self.model.transcribe(
            audio,
            language=lang,
            beam_size=5,
            vad_filter=True,
            initial_prompt=self.prompt,
            condition_on_previous_text=False,
            no_speech_threshold=0.5,
            log_prob_threshold=-1.0,
        )
        parts = [s.text.strip() for s in segments if s.no_speech_prob < 0.6]
        text = " ".join(parts).strip()
        if any(h in text.lower() for h in HALLUCINATIONS):
            return "", lang
        return text, lang