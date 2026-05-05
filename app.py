import time
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from scripts.mermaid_generator import generate_mermaid


BACKEND_URL = "http://localhost:8000"

st.set_page_config(layout="wide")
st.title("TGA - Live Architecture Visualizer")

st_autorefresh(interval=1000, key="tga_refresh")


if "diagram" not in st.session_state:
    st.session_state.diagram = "graph TD\nA[Waiting for data...]"

if "state" not in st.session_state:
    st.session_state.state = {}

if "zip_ready" not in st.session_state:
    st.session_state.zip_ready = False

if "zip_path" not in st.session_state:
    st.session_state.zip_path = ""

if "context_prompt" not in st.session_state:
    st.session_state.context_prompt = ""

if "processing_status" not in st.session_state:
    st.session_state.processing_status = {
        "state": "idle",
        "message": "Ready",
        "current_chunk": "",
        "chunks_processed": 0,
        "total_chunks": 0,
    }


def render_mermaid(mermaid_code: str):
    render_id = f"mermaid_{abs(hash(mermaid_code))}_{int(time.time() * 1000)}"
    html = f"""
    <html>
    <head>
        <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    </head>
    <body>
        <div id="{render_id}" class="mermaid">
            {mermaid_code}
        </div>

        <button onclick="downloadSVG()" style="margin-top: 12px;">
            Download SVG
        </button>

        <script>
            mermaid.initialize({{ startOnLoad: false }});
            mermaid.run({{ querySelector: "#{render_id}" }});

            function downloadSVG() {{
                const container = document.getElementById("{render_id}");
                const svg = container ? container.querySelector("svg") : null;
                if (!svg) return;

                const serializer = new XMLSerializer();
                const source = serializer.serializeToString(svg);
                const blob = new Blob([source], {{ type: "image/svg+xml;charset=utf-8" }});
                const url = URL.createObjectURL(blob);

                const link = document.createElement("a");
                link.href = url;
                link.download = "tga_architecture_diagram.svg";
                link.click();

                URL.revokeObjectURL(url);
            }}
        </script>
    </body>
    </html>
    """
    components.html(html, height=500)


def render_browser_voice_recorder():
    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: sans-serif;
                margin: 0;
            }}
            button {{
                margin-right: 8px;
                padding: 6px 10px;
                cursor: pointer;
            }}
            #status {{
                margin-top: 8px;
                font-size: 13px;
                color: #444;
            }}
        </style>
    </head>
    <body>
        <button id="startBtn">Start Recording</button>
        <button id="stopBtn" disabled>Stop & Process</button>
        <div id="status">Microphone ready</div>

        <script>
            const backendUrl = "{BACKEND_URL}";
            let mediaRecorder = null;
            let audioChunks = [];

            const startBtn = document.getElementById("startBtn");
            const stopBtn = document.getElementById("stopBtn");
            const statusEl = document.getElementById("status");

            startBtn.onclick = async () => {{
                try {{
                    await fetch(`${{backendUrl}}/status-event`, {{
                        method: "POST",
                        headers: {{ "Content-Type": "application/json" }},
                        body: JSON.stringify({{
                            state: "recording",
                            mode: "browser_voice",
                            message: "Recording voice in browser"
                        }})
                    }});

                    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                    audioChunks = [];
                    mediaRecorder = new MediaRecorder(stream);

                    mediaRecorder.ondataavailable = event => {{
                        if (event.data.size > 0) {{
                            audioChunks.push(event.data);
                        }}
                    }};

                    mediaRecorder.onstop = async () => {{
                        statusEl.innerText = "Uploading recording...";
                        await fetch(`${{backendUrl}}/status-event`, {{
                            method: "POST",
                            headers: {{ "Content-Type": "application/json" }},
                            body: JSON.stringify({{
                                state: "uploading",
                                mode: "browser_voice",
                                message: "Uploading browser recording"
                            }})
                        }});

                        const blob = new Blob(audioChunks, {{ type: "audio/webm" }});
                        const formData = new FormData();
                        formData.append("file", blob, "browser_recording.webm");

                        const uploadResponse = await fetch(`${{backendUrl}}/upload-file`, {{
                            method: "POST",
                            body: formData
                        }});

                        if (!uploadResponse.ok) {{
                            statusEl.innerText = "Upload failed";
                            return;
                        }}

                        statusEl.innerText = "Processing recording...";
                        const startResponse = await fetch(`${{backendUrl}}/start-session`, {{
                            method: "POST"
                        }});

                        if (startResponse.ok) {{
                            statusEl.innerText = "Recording sent. Diagram will update as speech is processed.";
                        }} else {{
                            statusEl.innerText = "Processing failed";
                        }}

                        stream.getTracks().forEach(track => track.stop());
                    }};

                    mediaRecorder.start();
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                    statusEl.innerText = "Recording...";
                }} catch (error) {{
                    statusEl.innerText = "Microphone permission failed";
                }}
            }};

            stopBtn.onclick = () => {{
                if (mediaRecorder && mediaRecorder.state !== "inactive") {{
                    mediaRecorder.stop();
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(html, height=92)


def poll_state():
    try:
        response = requests.get(f"{BACKEND_URL}/state", timeout=2)
        response.raise_for_status()

        current_state = response.json()
        st.session_state.state = current_state
        st.session_state.diagram = generate_mermaid(current_state)
    except requests.RequestException:
        pass


def poll_status():
    try:
        response = requests.get(f"{BACKEND_URL}/status", timeout=2)
        response.raise_for_status()
        st.session_state.processing_status = response.json()
    except requests.RequestException:
        st.session_state.processing_status = {
            "state": "offline",
            "message": "Backend status unavailable",
            "current_chunk": "",
            "chunks_processed": 0,
            "total_chunks": 0,
        }


def render_processing_panel(status):
    state_name = status.get("state", "idle")
    message = status.get("message", "Ready")
    mode = status.get("mode") or "none"
    current_chunk = status.get("current_chunk", "")
    chunks_processed = int(status.get("chunks_processed") or 0)
    total_chunks = int(status.get("total_chunks") or 0)

    if state_name in {
        "recording",
        "uploading",
        "uploaded",
        "processing",
        "transcribing",
        "extracting",
        "diagram_update",
        "transcribed_chunk",
        "generating_project",
    }:
        st.info(f"Working: {message}")
    elif state_name == "completed":
        st.success(message)
    elif state_name == "stopped":
        st.warning(message)
    elif state_name == "error":
        st.error(message)
    elif state_name == "offline":
        st.warning(message)
    else:
        st.caption(f"Status: {message}")

    cols = st.columns(3)
    cols[0].metric("Mode", mode)
    cols[1].metric("Stage", state_name)
    cols[2].metric("Chunks", f"{chunks_processed}/{total_chunks or '?'}")

    if total_chunks > 0:
        st.progress(min(chunks_processed / total_chunks, 1.0))
    elif state_name in {"transcribing", "extracting", "generating_project"}:
        st.progress(0.25)

    if current_chunk:
        st.markdown("**Current chunk being processed**")
        st.code(current_chunk, language="text")

with st.sidebar:
    st.title("Controls")

    st.subheader("Context Prompt")
    context = st.text_area(
        "System Context",
        value=st.session_state.context_prompt,
        placeholder="e.g. We are building a fintech app using Python + FastAPI",
    )
    st.session_state.context_prompt = context

    if st.button("Save Context"):
        requests.post(
            f"{BACKEND_URL}/set-context",
            json={"context": st.session_state.context_prompt},
        )
        st.success("Context saved")

    st.subheader("Text Input")
    user_input = st.text_area(
        "Enter architecture description",
        placeholder=(
            "Frontend talks to API gateway\n"
            "API gateway routes to auth service\n"
            "Auth service uses PostgreSQL"
        ),
    )

    if st.button("Generate Diagram"):
        if user_input.strip():
            requests.post(
                f"{BACKEND_URL}/start-session-text",
                json={"text": user_input},
            )
            st.success("Processing text...")

    st.subheader("Voice Input")
    uploaded_file = st.file_uploader(
        "Upload MP3/WAV/M4A/WEBM",
        type=["mp3", "wav", "m4a", "webm"],
    )

    if uploaded_file:
        if st.button("Process Audio"):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type or "application/octet-stream",
                )
            }
            upload_response = requests.post(f"{BACKEND_URL}/upload-file", files=files)

            if upload_response.status_code == 200:
                start_response = requests.post(f"{BACKEND_URL}/start-session")

                if start_response.status_code == 200:
                    st.success("Audio processing started")
                else:
                    st.error(start_response.json().get("error", "Audio processing failed"))
            else:
                st.error("Audio upload failed")

    st.caption("Or record directly from your browser microphone:")
    render_browser_voice_recorder()

    st.subheader("Session")

    if st.button("Stop Processing"):
        requests.post(f"{BACKEND_URL}/stop-session")

    if st.button("Reset Session"):
        requests.post(f"{BACKEND_URL}/reset-session")
        st.session_state.diagram = "graph TD\nA[Reset]"
        st.session_state.state = {}
        st.success("Reset done")

    st.subheader("Project Export")

    if st.button("Generate Project"):
        with st.spinner("Generating project..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/generate-scaffold",
                    stream=True,
                )

                if response.status_code == 200:
                    zip_path = "generated_project.zip"

                    with open(zip_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    st.session_state.zip_ready = True
                    st.session_state.zip_path = zip_path

                    st.success("Project generated successfully")
                else:
                    st.error("Generation failed")

            except Exception as e:
                st.error(f"Error: {e}")

    existing_zip = Path("generated_project.zip")
    if existing_zip.exists():
        st.session_state.zip_ready = True
        st.session_state.zip_path = str(existing_zip)

    if st.session_state.zip_ready and Path(st.session_state.zip_path).exists():
        with open(st.session_state.zip_path, "rb") as f:
            st.download_button(
                label="Download Project ZIP",
                data=f,
                file_name="generated_project.zip",
                mime="application/zip",
            )

    if st.button("Open Project Folder"):
        requests.get(f"{BACKEND_URL}/open-folder")


poll_state()
poll_status()


def render_entity_panel(state):
    st.subheader("Extracted Entities")

    if not state:
        st.info("No data yet...")
        return

    if state.get("services"):
        st.markdown("### Services")
        for service in state["services"]:
            st.markdown(f"- **{service}**")
        st.divider()

    if state.get("databases"):
        st.markdown("### Databases")
        for database in state["databases"]:
            st.markdown(f"- **{database}**")
        st.divider()

    if state.get("apis"):
        st.markdown("### APIs")
        for api in state["apis"]:
            st.markdown(f"- **{api}**")
        st.divider()

    if state.get("message_queues"):
        st.markdown("### Message Queues")
        for queue in state["message_queues"]:
            st.markdown(f"- **{queue}**")
        st.divider()

    if state.get("relationships"):
        st.markdown("### Relationships")
        for relationship in state["relationships"]:
            st.markdown(
                f"**{relationship['from']} -> {relationship['to']}** "
                f"({relationship.get('protocol', '-')})"
            )
        st.divider()


left, right = st.columns([2, 1])

with left:
    st.subheader("Processing Status")
    render_processing_panel(st.session_state.processing_status)

    st.subheader("Live Architecture Diagram")
    render_mermaid(st.session_state.diagram)

with right:
    render_entity_panel(st.session_state.state)
