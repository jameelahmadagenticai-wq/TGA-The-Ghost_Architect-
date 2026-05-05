"""
========================================
TGA - STATEFUL EXTRACTION PIPELINE (UPDATED)
========================================

Now supports:
✔ LLM (llama.cpp)
✔ External llm_engine (fallback)
✔ Real-time chunk processing
✔ Compatible with audio pipeline

========================================
"""

import multiprocessing
import json
from pathlib import Path

# OPTIONAL: llama.cpp
try:
    from llama_cpp import Llama
    USE_LLAMA = True
except:
    USE_LLAMA = False


# ========================================
# CONFIG
# ========================================
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "llm" / "model.gguf"
N_CTX = 4096
N_THREADS = multiprocessing.cpu_count()
OUTPUT_PATH = BASE_DIR / "output" / "architecture_state.json"

# OPTIONAL: external LLM fallback. Import it only when direct llama.cpp is
# unavailable, otherwise the GGUF model can be loaded twice.
if not USE_LLAMA:
    try:
        from scripts.llm_engine import extract_architecture
        USE_EXTERNAL_LLM = True
    except Exception:
        USE_EXTERNAL_LLM = False
else:
    extract_architecture = None
    USE_EXTERNAL_LLM = False


# ========================================
# LOAD MODEL (ONLY IF AVAILABLE)
# ========================================
if USE_LLAMA:
    print("🔄 Loading model...")
    llm = Llama(
        model_path=str(MODEL_PATH),
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        verbose=False
    )
    print("✅ Model loaded")
else:
    llm = None
    print("⚠️ llama.cpp not found, using fallback engine")


# ========================================
# SYSTEM PROMPT
# ========================================
SYSTEM_PROMPT = """
You are a Senior System Architect.

Extract ONLY structured architecture from text.

Rules:
- Return ONLY JSON
- No explanation
- No markdown

Extract:
- services
- databases
- apis
- message_queues
- relationships

Relationship format:
{"from": "", "to": "", "protocol": ""}

Return:
{
  "services": [],
  "databases": [],
  "apis": [],
  "message_queues": [],
  "relationships": []
}
"""


BASE_MESSAGES = [
    {"role": "system", "content": SYSTEM_PROMPT}
]


# ========================================
# GLOBAL STATE
# ========================================
state = {
    "services": set(),
    "databases": set(),
    "apis": set(),
    "message_queues": set(),
    "relationships": []
}


# ========================================
# SAFE PARSER
# ========================================
def safe_parse(output):
    try:
        return json.loads(output)
    except:
        print("⚠️ Invalid JSON skipped")
        return None


# ========================================
# NORMALIZER
# ========================================
def normalize_item(item):
    if isinstance(item, str):
        return item.lower().strip()
    elif isinstance(item, dict):
        return item.get("name", "").lower().strip()
    return ""


# ========================================
# MERGE STATE
# ========================================
def merge_state(new_data):
    if not new_data:
        return

    for key in ["services", "databases", "apis", "message_queues"]:
        items = new_data.get(key, [])

        for item in items:
            clean = normalize_item(item)
            if clean:
                state[key].add(clean)

    existing = set(
        (r["from"], r["to"], r["protocol"])
        for r in state["relationships"]
    )

    for rel in new_data.get("relationships", []):
        from_val = normalize_item(rel.get("from", ""))
        to_val = normalize_item(rel.get("to", ""))
        protocol = normalize_item(rel.get("protocol", ""))

        rel_tuple = (from_val, to_val, protocol)

        if rel_tuple not in existing:
            state["relationships"].append({
                "from": from_val,
                "to": to_val,
                "protocol": protocol
            })


# ========================================
# SAVE STATE
# ========================================
def save_state():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    serializable = {
        "services": list(state["services"]),
        "databases": list(state["databases"]),
        "apis": list(state["apis"]),
        "message_queues": list(state["message_queues"]),
        "relationships": state["relationships"]
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(serializable, f, indent=2)

    print("💾 State saved")


# ========================================
# CORE EXTRACTION LOGIC (UPDATED)
# ========================================
def run_llm_extraction(text):
    """
    Chooses best available engine
    """

    # Priority 1: llama.cpp
    if USE_LLAMA and llm:
        messages = BASE_MESSAGES + [
            {"role": "user", "content": text}
        ]

        response = llm.create_chat_completion(
            messages=messages,
            max_tokens=300,
            temperature=0.0,
            top_p=0.9,
            repeat_penalty=1.1
        )

        raw_output = response["choices"][0]["message"]["content"].strip()
        print("🧠 LLM Output:", raw_output)

        return safe_parse(raw_output)

    # Priority 2: fallback engine
    if USE_EXTERNAL_LLM:
        print("🧠 Using fallback LLM engine")
        return extract_architecture(text)

    print("⚠️ No LLM available")
    return None


# ========================================
# PROCESS CHUNK (MAIN ENTRY)
# ========================================
def process_chunk(chunk_text, index):
    print(f"\n📦 Processing chunk {index+1}...")
    print(f"📝 Input: {chunk_text}")

    parsed = run_llm_extraction(chunk_text)

    merge_state(parsed)
    save_state()
