from __future__ import annotations

from typing import Callable

import numpy as np
import openwakeword
import sounddevice as sd
import webrtcvad
from openwakeword.model import Model

SAMPLE_RATE = 16000          # Hz, required by openWakeWord and Whisper
FRAME = 1280                 # samples (80 ms), block size for openWakeWord
VAD_FRAME = 320              # samples (20 ms), a frame size webrtcvad accepts
MIN_SPEECH_FRAMES = 2        # fewer speech frames than this is treated as noise


class VoiceListener:
    def __init__(
        self,
        wake_model: str = "alexa",
        threshold: float = 0.5,
        vad_level: int = 2,
        silence_sec: float = 0.7,
        no_speech_sec: float = 4.0,
        max_sec: float = 10.0,
    ) -> None:
        try:
            openwakeword.utils.download_models()   # needs network only the first time
        except Exception as exc:                   # noqa: BLE001
            print(f"[warn] could not check openWakeWord models: {exc}")
        self.oww = Model(wakeword_models=[wake_model], inference_framework="onnx")
        self.vad = webrtcvad.Vad(vad_level)
        self.threshold = threshold
        self.silence_sec = silence_sec
        self.no_speech_sec = no_speech_sec
        self.max_sec = max_sec

    def _open_stream(self) -> sd.InputStream:
        return sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME
        )

    def _is_speech(self, frame: np.ndarray) -> bool:
        # Split one 80 ms block into 20 ms VAD frames, any speech counts
        return any(
            self.vad.is_speech(frame[i:i + VAD_FRAME].tobytes(), SAMPLE_RATE)
            for i in range(0, FRAME, VAD_FRAME)
        )

    def wait_for_command(
        self, on_wake: Callable[[], None] | None = None
    ) -> np.ndarray | None:
        """Block until the wake word, then record one phrase (float32, -1..1)."""
        self.oww.reset()
        with self._open_stream() as stream:
            while True:
                frame = stream.read(FRAME)[0][:, 0]
                scores = self.oww.predict(frame)
                if scores and max(scores.values()) >= self.threshold:
                    break
        if on_wake:
            on_wake()
        with self._open_stream() as stream:
            return self._record_phrase(stream)

    def _record_phrase(self, stream) -> np.ndarray | None:
        # Stop after a pause following speech, or give up if nobody speaks
        frames: list[np.ndarray] = []
        speech_frames = 0
        silence = elapsed = 0.0
        step = FRAME / SAMPLE_RATE

        while elapsed < self.max_sec:
            frame = stream.read(FRAME)[0][:, 0]
            frames.append(frame)
            elapsed += step

            if self._is_speech(frame):
                speech_frames += 1
                silence = 0.0
            else:
                silence += step

            if speech_frames and silence >= self.silence_sec:
                break
            if not speech_frames and elapsed >= self.no_speech_sec:
                return None

        if speech_frames < MIN_SPEECH_FRAMES:
            return None
        return np.concatenate(frames).astype(np.float32) / 32768.0