"""
========================================
TGA - STEP 1.4 (CHUNKING + TIMESTAMPS)
========================================

Flow:
Audio → Whisper segments → Merge → Token chunking → JSON

Replaceable Sections:
[TOKEN_LIMIT]
[TRANSCRIPTION_SETTINGS]
========================================
"""

import json
from faster_whisper import WhisperModel


# ========================================
# [CONFIG] 🔁
# ========================================
INPUT_FILE = "../input/sample.wav"
OUTPUT_FILE = "../output/transcript_chunks.json"

MODEL_SIZE = "small"
TOKEN_LIMIT = 300  # 200–400 ideal
# Purpose:
# - Control chunk size for LLM


# ========================================
# MODEL LOAD
# ========================================
model = WhisperModel(MODEL_SIZE, compute_type="int8")


# ========================================
# TRANSCRIBE WITH TIMESTAMPS
# ========================================
def transcribe_with_timestamps(file_path):
    segments, _ = model.transcribe(
        file_path,
        language="en",
        word_timestamps=True
    )
    return list(segments)
# Purpose:
# - Extract start/end time for each segment


# ========================================
# FORMAT TIME
# ========================================
def format_time(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"
# Purpose:
# - Convert seconds → MM:SS


# ========================================
# GROUP INTO CHUNKS
# ========================================
def chunk_segments(segments):
    chunks = []
    current_text = ""
    start_time = None
    chunk_id = 1

    for seg in segments:
        text = seg.text.strip()

        if not text:
            continue

        if start_time is None:
            start_time = seg.start

        current_text += " " + text

        # Approx token count (1 token ≈ 4 chars)
        token_estimate = len(current_text) // 4

        if token_estimate >= TOKEN_LIMIT:
            chunks.append({
                "id": chunk_id,
                "time": f"{format_time(start_time)}-{format_time(seg.end)}",
                "text": current_text.strip()
            })

            chunk_id += 1
            current_text = ""
            start_time = None

    # leftover chunk
    if current_text:
        chunks.append({
            "id": chunk_id,
            "time": f"{format_time(start_time)}-{format_time(segments[-1].end)}",
            "text": current_text.strip()
        })

    return chunks


# ========================================
# SAVE JSON
# ========================================
def save_chunks(chunks):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"\n✅ Chunked transcript saved at: {OUTPUT_FILE}")


# ========================================
# MAIN
# ========================================
def main():
    print("🧠 Transcribing with timestamps...")
    segments = transcribe_with_timestamps(INPUT_FILE)

    print("✂️ Creating chunks...")
    chunks = chunk_segments(segments)

    print("💾 Saving JSON...")
    save_chunks(chunks)


if __name__ == "__main__":
    main()