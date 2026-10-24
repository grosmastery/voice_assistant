from __future__ import annotations

import io
import os
import wave
import winsound
from collections import OrderedDict

from piper import PiperVoice

LEAD_SILENCE = 0.35   # seconds of silence before a phrase, so the sound card wakes up first
CACHE_SIZE = 50       # how many rendered phrases to keep in memory


class Speaker:
    def __init__(self, voice_path: str, lead_silence: float = LEAD_SILENCE) -> None:
        if not os.path.exists(voice_path):
            raise FileNotFoundError(
                f"Piper voice not found: {voice_path}. "
                "Download it: python -m piper.download_voices <name> --data-dir models/piper"
            )
        self.voice = PiperVoice.load(voice_path)
        self.lead_silence = lead_silence
        self._cache: OrderedDict[str, bytes] = OrderedDict()

    def _render(self, text: str) -> bytes:
        """Synthesize text into WAV bytes with leading silence."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self.voice.synthesize_wav(text, wf)
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            params = r.getparams()
            frames = r.readframes(r.getnframes())

        silence = b"\x00" * (
            int(params.framerate * self.lead_silence)
            * params.sampwidth * params.nchannels
        )
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setparams(params)
            w.writeframes(silence + frames)
        return out.getvalue()

    def _get(self, text: str) -> bytes:
        # Simple LRU cache
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        data = self._render(text)
        self._cache[text] = data
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return data

    def warm_up(self, phrases: list[str]) -> None:
        for phrase in phrases:
            self._get(phrase)

    def say(self, text: str) -> None:
        if not text or not text.strip():
            return
        winsound.PlaySound(self._get(text), winsound.SND_MEMORY)   # blocks until done