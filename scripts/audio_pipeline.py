# scripts/audio_pipeline.py

from faster_whisper import WhisperModel

# ==============================
# LOAD MODEL (CPU OPTIMIZED)
# ==============================
model = WhisperModel(
    "base",           # you can change to "small" for better accuracy
    compute_type="int8"  # CPU optimization
)


# ==============================
# TRANSCRIBE FILE (STREAMING STYLE)
# ==============================
def transcribe_file(file_path: str):
    """
    Generator that yields transcript chunks
    """

    segments, _ = model.transcribe(file_path)

    for segment in segments:
        text = segment.text.strip()

        if text:
            print(f"🎤 Chunk: {text}")
            yield text