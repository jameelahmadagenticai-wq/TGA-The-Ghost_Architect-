from pathlib import Path
import asyncio
import json
import os
import platform
import subprocess
import zipfile

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

from scripts.architecture_extraction_pipeline import process_chunk, state
from scripts.audio_pipeline import transcribe_file
from scripts.blueprint_generator import generate_blueprint, save_blueprint
from scripts.manifesto_generator import generate_manifesto, save_manifesto
from scripts.mermaid_generator import generate_mermaid
from scripts.scaffold_generator import generate_project


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "input" / "uploads"

clients = []
is_running = False
CONTEXT_PROMPT = ""
latest_audio_path = None
processing_status = {
    "state": "idle",
    "mode": None,
    "message": "Ready",
    "current_chunk": "",
    "chunks_processed": 0,
    "total_chunks": 0,
    "last_error": "",
}


async def broadcast_event(data):
    for queue in clients:
        await queue.put(data)


def get_current_state():
    return {
        "services": list(state["services"]),
        "databases": list(state["databases"]),
        "apis": list(state["apis"]),
        "message_queues": list(state["message_queues"]),
        "relationships": state["relationships"],
    }


def with_context(text):
    if CONTEXT_PROMPT.strip():
        return f"{CONTEXT_PROMPT.strip()}\n\n{text}"
    return text


def update_status(**changes):
    processing_status.update(changes)


def reset_status(message="Ready"):
    update_status(
        state="idle",
        mode=None,
        message=message,
        current_chunk="",
        chunks_processed=0,
        total_chunks=0,
        last_error="",
    )


def zip_project(folder_path, zip_path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, relative_path)


def open_folder(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def next_audio_chunk(iterator):
    try:
        return next(iterator)
    except StopIteration:
        return None


async def process_single_chunk(chunk, index):
    update_status(
        state="extracting",
        message=f"Extracting architecture from chunk {index + 1}",
        current_chunk=chunk,
        chunks_processed=index,
    )

    await asyncio.to_thread(process_chunk, with_context(chunk), index)

    current_state = get_current_state()
    mermaid = generate_mermaid(current_state)

    update_status(
        state="diagram_update",
        message=f"Diagram updated after chunk {index + 1}",
        chunks_processed=index + 1,
    )

    await broadcast_event({
        "event_type": "state_update",
        "data": current_state,
    })

    await broadcast_event({
        "event_type": "diagram_update",
        "diagram": mermaid,
    })


async def process_text_chunks(chunks, delay):
    global is_running

    update_status(
        state="processing",
        mode="text",
        message="Processing text input",
        current_chunk="",
        chunks_processed=0,
        total_chunks=len(chunks),
        last_error="",
    )

    for i, chunk in enumerate(chunks):
        if not is_running:
            update_status(state="stopped", message="Processing stopped by user")
            break

        await process_single_chunk(chunk, i)
        await asyncio.sleep(delay)
    else:
        is_running = False
        update_status(
            state="completed",
            message="Text processing completed",
            current_chunk="",
            chunks_processed=len(chunks),
            total_chunks=len(chunks),
        )


async def process_audio_chunks(file_path, delay):
    global is_running

    update_status(
        state="transcribing",
        mode="audio",
        message="Transcribing audio",
        current_chunk="",
        chunks_processed=0,
        total_chunks=0,
        last_error="",
    )

    iterator = transcribe_file(file_path)
    index = 0

    while is_running:
        chunk = await asyncio.to_thread(next_audio_chunk, iterator)

        if chunk is None:
            break

        update_status(
            state="transcribed_chunk",
            message=f"Transcribed audio chunk {index + 1}",
            current_chunk=chunk,
            chunks_processed=index,
            total_chunks=index + 1,
        )

        await process_single_chunk(chunk, index)
        index += 1
        await asyncio.sleep(delay)

    if is_running:
        is_running = False
        update_status(
            state="completed",
            message="Audio processing completed",
            current_chunk="",
            chunks_processed=index,
            total_chunks=index,
        )
    else:
        update_status(state="stopped", message="Audio processing stopped by user")


@app.get("/stream")
async def stream():
    queue = asyncio.Queue()
    clients.append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
        except asyncio.CancelledError:
            if queue in clients:
                clients.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/set-context")
async def set_context(data: dict):
    global CONTEXT_PROMPT
    CONTEXT_PROMPT = data.get("context", "")
    return {"status": "context set"}


@app.post("/reset-session")
async def reset_session():
    global is_running

    is_running = False
    state["services"].clear()
    state["databases"].clear()
    state["apis"].clear()
    state["message_queues"].clear()
    state["relationships"].clear()
    reset_status("Session reset")

    return {"status": "reset"}


@app.post("/start-session-text")
async def start_session_text(data: dict):
    global is_running

    text = data.get("text", "")
    if not text.strip():
        return {"error": "No text provided"}

    is_running = True
    chunks = [line.strip() for line in text.splitlines() if line.strip()]
    asyncio.create_task(process_text_chunks(chunks, delay=0.3))

    return {"status": "text processing started"}


@app.post("/start-session")
async def start_session():
    global is_running

    if not latest_audio_path:
        update_status(
            state="error",
            message="No uploaded or recorded audio found",
            last_error="No uploaded audio found",
        )
        return {"error": "No uploaded audio found"}

    is_running = True

    async def run_pipeline():
        await process_audio_chunks(str(latest_audio_path), delay=0.5)

    asyncio.create_task(run_pipeline())

    return {"status": "audio processing started", "file": str(latest_audio_path)}


@app.post("/stop-session")
async def stop_session():
    global is_running
    is_running = False
    update_status(state="stopped", message="Processing stopped by user")
    return {"status": "stopped"}


@app.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    global latest_audio_path

    contents = await file.read()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = os.path.basename(file.filename or "meeting_audio")
    if "." not in safe_name:
        safe_name = f"{safe_name}.webm"

    path = UPLOAD_DIR / safe_name

    with open(path, "wb") as f:
        f.write(contents)

    latest_audio_path = path
    update_status(
        state="uploaded",
        mode="audio",
        message=f"Audio uploaded: {safe_name}",
        current_chunk="",
        chunks_processed=0,
        total_chunks=0,
        last_error="",
    )
    return {"status": "file received", "filename": safe_name}


@app.get("/state")
async def get_state():
    return get_current_state()


@app.get("/status")
async def get_status():
    return processing_status


@app.post("/status-event")
async def status_event(data: dict):
    update_status(
        state=data.get("state", processing_status["state"]),
        mode=data.get("mode", processing_status["mode"]),
        message=data.get("message", processing_status["message"]),
        current_chunk=data.get("current_chunk", processing_status["current_chunk"]),
    )
    return {"status": "updated"}


@app.post("/generate-scaffold")
async def generate_scaffold():
    current_state = get_current_state()

    update_status(
        state="generating_project",
        mode="export",
        message="Generating blueprint",
        current_chunk="",
        last_error="",
    )

    blueprint = generate_blueprint(current_state)
    save_blueprint(blueprint)

    update_status(state="generating_project", message="Generating Architect's Manifesto")
    manifesto = await asyncio.to_thread(generate_manifesto, current_state)
    save_manifesto(manifesto)

    update_status(state="generating_project", message="Creating project scaffold")
    await asyncio.to_thread(generate_project)

    project_path = BASE_DIR / "generated_project"
    zip_path = BASE_DIR / "generated_project.zip"
    update_status(state="generating_project", message="Packaging generated project ZIP")
    zip_project(project_path, zip_path)

    update_status(state="completed", message="Project ZIP generated")

    return FileResponse(
        path=zip_path,
        filename="generated_project.zip",
        media_type="application/zip",
    )


@app.get("/open-folder")
async def open_generated_folder():
    path = BASE_DIR / "generated_project"
    open_folder(str(path))
    return {"status": "opened"}
