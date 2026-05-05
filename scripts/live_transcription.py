import sounddevice as sd  # Capture mic audio
import numpy as np        # Handle audio arrays
import queue              # Buffer audio chunks
import threading          # Background processing
from faster_whisper import WhisperModel

# ==============================
# MODEL LOAD
# ==============================
model = WhisperModel("small", compute_type="int8")
# Purpose: Loads CPU-optimized speech-to-text model


# ==============================
# CONFIG
# ==============================
SAMPLE_RATE = 16000
CHUNK_DURATION = 5  # seconds
CHUNK_SIZE = SAMPLE_RATE * CHUNK_DURATION

audio_queue = queue.Queue()
is_recording = False


# ==============================
# AUDIO CALLBACK (NON-BLOCKING)
# ==============================
def audio_callback(indata, frames, time, status):
    if status:
        print("⚠️ Audio error:", status)

    audio_queue.put(indata.copy())
# Purpose: Push mic audio into queue without blocking stream


# ==============================
# TRANSCRIPTION WORKER
# ==============================
def process_audio():
    print("🧠 Transcription thread started...")

    buffer = np.array([], dtype=np.float32)

    while is_recording or not audio_queue.empty():
        try:
            chunk = audio_queue.get(timeout=1)
            buffer = np.concatenate((buffer, chunk.flatten()))

            # Process when enough audio collected
            if len(buffer) >= CHUNK_SIZE:
                segment_audio = buffer[:CHUNK_SIZE]
                buffer = buffer[CHUNK_SIZE:]

                # ==============================
                # SILENCE FILTER
                # ==============================
                if np.abs(segment_audio).mean() < 0.01:
                    continue
                # Purpose: Skip silent/noisy chunks

                # ==============================
                # TRANSCRIPTION
                # ==============================
                segments, _ = model.transcribe(
                    segment_audio,
                    language="en",
                    vad_filter=True
                )
                # Purpose:
                # - language="en" → avoid random languages
                # - vad_filter=True → ignore non-speech

                # ==============================
                # OUTPUT CLEANING
                # ==============================
                for segment in segments:
                    text = segment.text.strip()

                    if text and len(text) > 3:
                        print(f"[LIVE] {text}")
                # Purpose: Remove garbage/short noise text

        except queue.Empty:
            continue


# ==============================
# START RECORDING
# ==============================
def start_recording():
    global is_recording
    is_recording = True

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            callback=audio_callback
        )

        stream.start()
        print("🎤 Recording started...")

        thread = threading.Thread(target=process_audio, daemon=True)
        thread.start()
        # Purpose: Run transcription in background safely

        return stream, thread

    except Exception as e:
        print("❌ Microphone error:", str(e))
        return None, None


# ==============================
# STOP RECORDING
# ==============================
def stop_recording(stream):
    global is_recording
    is_recording = False

    if stream:
        stream.stop()
        stream.close()

    print("🛑 Recording stopped.")
# Purpose: Clean shutdown of mic + thread


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    stream, thread = start_recording()

    if stream:
        input("Press ENTER to stop...\n")
        stop_recording(stream)