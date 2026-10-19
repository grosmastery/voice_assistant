import numpy as np
import sounddevice as sd
import webrtcvad
import openwakeword
from openwakeword.model import Model

SAMPLE_RATE = 16000
FRAME = 1280
VAD_FRAME = 320

class VoiceListener:
    def __init__(self, wake_model="alexa", threshold=0.5, vad_level=2, silence_sec=0.4, no_speech_sec=4.0, max_sec=10.0):
        openwakeword.utils.download_models()
        self.oww = Model(wakeword_models=[wake_model], inference_framework="onnx")
        self.vad = webrtcvad.Vad(vad_level)
        self.threshold = threshold
        self.silence_sec = silence_sec
        self.no_speech_sec = no_speech_sec
        self.max_sec = max_sec

    def wait_for_command(self, on_wake=None):
        self.oww.reset()
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME) as stream:
            while True:
                frame = stream.read(FRAME)[0][:, 0]
                scores = self.oww.predict(frame)
                if max(scores.values()) >= self.threshold:
                    break
        if on_wake:
            on_wake()
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                dtype="int16", blocksize=FRAME) as stream:
            return self._record_phrase(stream)

    def _record_phrase(self, stream):
        frames, heard, silence, elapsed = [], False, 0.0, 0.0
        step = FRAME / SAMPLE_RATE
        while elapsed < self.max_sec:
            frame = stream.read(FRAME)[0][:, 0]
            frames.append(frame)
            elapsed += step
            speech = any(self.vad.is_speech(frame[i:i+VAD_FRAME].tobytes(), SAMPLE_RATE) for i in range(0, FRAME, VAD_FRAME))
            if speech:
                heard, silence = True, 0.0
            else:
                silence += step
            if heard and silence >= self.silence_sec:
                break
            if not heard and silence >= self.no_speech_sec:
                return None
        return np.concatenate(frames).astype(np.float32) / 32768.0