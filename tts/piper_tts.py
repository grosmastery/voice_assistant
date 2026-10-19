import io
import wave
import winsound

from piper import PiperVoice

LEAD_SILENCE = 0.35


class Speaker:
    def __init__(self, voice_path: str):
        self.voice = PiperVoice.load(voice_path)
        self._cache = {}

    def _render(self, text: str) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self.voice.synthesize_wav(text, wf)
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            params = r.getparams()
            frames = r.readframes(r.getnframes())
        silence = b"\x00" * (int(params.framerate * LEAD_SILENCE)
                             * params.sampwidth * params.nchannels)
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setparams(params)
            w.writeframes(silence + frames)
        return out.getvalue()

    def say(self, text: str):
        if text not in self._cache:
            if len(self._cache) > 50:
                self._cache.clear()
            self._cache[text] = self._render(text)
        winsound.PlaySound(self._cache[text], winsound.SND_MEMORY)