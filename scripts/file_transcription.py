"""
========================================
TGA - STEP 1.3 (FILE TRANSCRIPTION)
========================================

Flow:
Load → Normalize → Split → Transcribe → Filter → Save

Replaceable Sections:
[CONFIG]
[TRANSCRIPTION_SETTINGS]
[FILTER_LOGIC]
========================================
"""

import os
from pydub import AudioSegment
from faster_whisper import WhisperModel
from tqdm import tqdm


# ========================================
# [CONFIG]  🔁 (You can replace this later)
# ========================================
INPUT_FILE = "../input/sample.mp3"
OUTPUT_FILE = "../output/transcript_raw.txt"
CHUNK_DURATION_MS = 30 * 1000
MODEL_SIZE = "small"
# Purpose:
# - Input/Output paths
# - Chunk size control
# - Model selection


# ========================================
# MODEL LOAD
# ========================================
model = WhisperModel(MODEL_SIZE, compute_type="int8")
# Purpose: Load CPU-optimized Whisper


# ========================================
# LOAD + NORMALIZE AUDIO
# ========================================
def load_and_convert(file_path):
    audio = AudioSegment.from_file(file_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    return audio
# Purpose:
# - Convert any format → Whisper-friendly


# ========================================
# SPLIT AUDIO
# ========================================
def split_audio(audio):
    return [
        audio[i:i + CHUNK_DURATION_MS]
        for i in range(0, len(audio), CHUNK_DURATION_MS)
    ]
# Purpose:
# - Break into manageable chunks


# ========================================
# [TRANSCRIPTION_SETTINGS] 🔁
# ========================================
def transcribe_audio(temp_path):
    segments, _ = model.transcribe(
        temp_path,
        language="en",
        vad_filter=True
    )
    return segments
# Purpose:
# - Central place to tweak model behavior
# - You can add beam_size, temperature later


# ========================================
# [FILTER_LOGIC] 🔁
# ========================================
def filter_text(segment):
    text = segment.text.strip()

    if (
        text
        and len(text) > 3
        and segment.avg_logprob > -1.0
        and text.lower() not in ["you", "uh", "um"]
    ):
        return text

    return None
# Purpose:
# - Remove noise / hallucinations
# - Improve transcript quality


# ========================================
# TRANSCRIBE PIPELINE
# ========================================
def transcribe_chunks(chunks):
    transcripts = []

    for i, chunk in enumerate(tqdm(chunks, desc="Processing Audio")):
        temp_path = f"temp_chunk_{i}.wav"

        # Export chunk
        chunk.export(temp_path, format="wav")

        # Transcribe
        segments = transcribe_audio(temp_path)

        # Apply filtering
        for seg in segments:
            clean_text = filter_text(seg)
            if clean_text:
                transcripts.append(clean_text)

        # Cleanup
        os.remove(temp_path)

    return transcripts


# ========================================
# SAVE OUTPUT
# ========================================
def save_transcript(transcripts):
    os.makedirs("../output", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for line in transcripts:
            f.write(line + "\n")

    print(f"\n✅ Transcript saved at: {OUTPUT_FILE}")


# ========================================
# MAIN
# ========================================
def main():
    print("📂 Loading audio...")
    audio = load_and_convert(INPUT_FILE)

    print("✂️ Splitting into chunks...")
    chunks = split_audio(audio)

    print("🧠 Transcribing...")
    transcripts = transcribe_chunks(chunks)

    print("💾 Saving output...")
    save_transcript(transcripts)


if __name__ == "__main__":
    main()