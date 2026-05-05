# scripts/convert.py
from pydub import AudioSegment

audio = AudioSegment.from_file("../input/sample.mp3")
audio = audio.set_frame_rate(16000).set_channels(1)
audio.export("../input/sample.wav", format="wav")