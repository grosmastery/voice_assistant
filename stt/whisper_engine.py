from __future__ import annotations

import glob
import os

import ctranslate2
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


def _add_cuda_dll_dirs() -> None:
    """Make pip-installed cuBLAS/cuDNN DLLs (nvidia-*-cu12) visible to ctranslate2."""
    try:
        import nvidia
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in glob.glob(os.path.join(base, "*", "bin")):
            os.add_dll_directory(bin_dir)
            # cuDNN loads its sub-libraries via PATH, add_dll_directory alone is not enough
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


if os.name == "nt":
    _add_cuda_dll_dirs()


def _warm_up(model: WhisperModel) -> None:
    # Runs the model once, so CUDA libraries load now and not on the first command
    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32),
                                   language="en", beam_size=1)
    list(segments)


class WhisperSTT:
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        compute_type: str = "float16",
        cpu_model: str = "small",
        beam_size: int = 5,
        vad_filter: bool = False,
        app_names: list[str] | None = None,
    ) -> None:
        """device: "auto" / "cuda" use the GPU if possible, "cpu" forces the CPU.

        model_size and compute_type are for the GPU; on the CPU (forced or as a
        fallback) cpu_model runs with int8, since big models are too slow there.
        """
        self.beam_size = beam_size
        self.vad_filter = vad_filter   # off by default: the listener already cut the silence
        self.model, self.description = self._load(model_size, device,
                                                  compute_type, cpu_model)
        names = app_names if app_names else APPS
        self.prompt: str = (
            "Open Warcraft. Відкрий Warcraft. Start Battle.net. "
            "Запусти Battle.net. Pause the music. Постав музику на паузу. "
            "Close Steam. Quit Spotify. Close Dota 2. Закрий Steam. "
            + " ".join(names)
        )

    @staticmethod
    def _load(model_size: str, device: str, compute_type: str,
              cpu_model: str) -> tuple[WhisperModel, str]:
        if device in ("auto", "cuda"):
            if ctranslate2.get_cuda_device_count() > 0:
                try:
                    model = WhisperModel(model_size, device="cuda",
                                         compute_type=compute_type)
                    _warm_up(model)
                    return model, f"{model_size} · cuda {compute_type}"
                except Exception as exc:  # noqa: BLE001  any GPU problem -> CPU
                    print(f"[stt] GPU failed, falling back to CPU: {exc}")
            else:
                print("[stt] no CUDA GPU found, using CPU")
        model = WhisperModel(cpu_model, device="cpu", compute_type="int8")
        return model, f"{cpu_model} · cpu int8"

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
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
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