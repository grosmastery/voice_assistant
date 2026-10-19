import numpy as np
from faster_whisper import WhisperModel


ALLOWED = ("en", "uk")
PRIORITY = {"en": 1.0, "uk": 1.0}
APPS = ["Warcraft", "Battle.net", "Opera GX", "Spotify", "Steam", "Dota 2", "Hearthstone", "VS Code"]
HALLUCINATIONS = (
    "thanks for watching", "thank you for watching", "see you in the next",
    "subscribe", "subtitles by", "дякую за перегляд", "підписуйтесь",
    "продовження слідує", "субтитри",
)


class WhisperSTT:
    def __init__(self, model_size="small", device="cpu", compute_type="int8"):
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.promt = (
            "Open Warcraft. Відкрий Warcraft. Start Battle.net. "
            "Запусти Battle.net. Pause the music. Постав музику на паузу. "
            "Close Steam. Quit Spotify. Close Dota 2. Закрий Steam. "
            + " ".join(APPS)
        )

    def _pick_language(self, audio: np.ndarray) -> str:
        _, _, probs =self.model.detect_language(audio)
        scores = {l: p * PRIORITY[l] for l, p in probs if l in ALLOWED}
        return max(scores, key=scores.get)

    def transcribe(self, audio: np.ndarray) -> tuple[str, str]:
        lang = self._pick_language(audio)
        segments, _ = self.model.transcribe(
            audio, language=lang, beam_size=5, vad_filter=True,
            initial_prompt=self.promt,
            condition_on_previous_text=False,
            no_speech_threshold=0.5,
            log_prob_threshold=-1.0,
        )
        parts = [s.text.strip() for s in segments if s.no_speech_prob < 0.6]
        text = " ".join(parts).strip()
        if any(h in text.lower() for h in HALLUCINATIONS):
            return "", lang
        return text, lang