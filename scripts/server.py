"""
========================================
TGA - STEP 3.2 (LIVE SSE SERVER)
========================================

Flow:
Chunk → Process → State → Mermaid → SSE Push

Endpoints:
/stream → live updates
/start → trigger pipeline
========================================
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json

# Import your existing logic
from architecture_extraction_pipeline import process_chunk, state
from mermaid_generator import generate_mermaid


app = FastAPI()

# ========================================
# GLOBAL EVENT QUEUE
# ========================================
event_queue = asyncio.Queue()


# ========================================
# EVENT PUSHER
# ========================================
async def push_event(data):
    await event_queue.put(data)


# ========================================
# SSE STREAM ENDPOINT
# ========================================
@app.get("/stream")
async def stream():

    async def event_generator():
        while True:
            data = await event_queue.get()
            yield f"data: {json.dumps(data)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ========================================
# PIPELINE RUNNER
# ========================================
CHUNKS = [
    "Frontend talks to API gateway.",
    "API gateway routes to auth service.",
    "Auth service uses PostgreSQL."
]


@app.get("/start")
async def start_pipeline():

    for i, chunk in enumerate(CHUNKS):

        # Step 1: Process chunk (updates state internally)
        process_chunk(chunk, i)

        # Step 2: Generate diagram
        mermaid = generate_mermaid({
            "services": list(state["services"]),
            "databases": list(state["databases"]),
            "apis": list(state["apis"]),
            "message_queues": list(state["message_queues"]),
            "relationships": state["relationships"]
        })

        # Step 3: Send updates
        await push_event({
            "event_type": "state_update",
            "data": {
                "services": list(state["services"]),
                "databases": list(state["databases"]),
                "apis": list(state["apis"]),
                "message_queues": list(state["message_queues"]),
                "relationships": state["relationships"]
            }
        })

        await push_event({
            "event_type": "diagram_update",
            "data": mermaid
        })

        await asyncio.sleep(1)  # simulate delay

    return {"status": "processing started"}