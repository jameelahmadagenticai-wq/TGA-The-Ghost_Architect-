from faster_whisper import WhisperModel

model = WhisperModel("small", compute_type="int8")

audio_file = "../input/sample.wav"

segments, info = model.transcribe(audio_file)

print("Detected language:", info.language)
print("\nTranscription:\n")

for segment in segments:
    print(f"[{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")