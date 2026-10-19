import io
import subprocess
import sys
import wave
import winsound

from piper import PiperVoice

VOICES = [
    "en_US-hfc_female-medium",
    "en_US-kristin-medium",
    "en_US-lessac-high",
    "en_GB-jenny_dioco-medium",
    "en_GB-cori-high",
    "en_US-ryan-high",
]
PHRASE = "Opening Battle.net. It's nine thirty in the evening, and the weather is clear."

for name in VOICES:
    subprocess.run([sys.executable, "-m", "piper.download_voices", name,
                    "--data-dir", "models/piper"], check=True)
    voice = PiperVoice.load(f"models/piper/{name}.onnx")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        voice.synthesize_wav(PHRASE, wf)
    print("Грає:", name)
    winsound.PlaySound(buf.getvalue(), winsound.SND_MEMORY)