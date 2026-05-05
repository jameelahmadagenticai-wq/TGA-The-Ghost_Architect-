# scripts/llm_engine.py

from llama_cpp import Llama
import multiprocessing
import json

# ==============================
# CONFIG
# ==============================
MODEL_PATH = "models/llm/model.gguf"
N_CTX = 4096
N_THREADS = multiprocessing.cpu_count()

# ==============================
# LOAD MODEL
# ==============================
print("🧠 Loading LLM...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=N_CTX,
    n_threads=N_THREADS,
    verbose=False
)
print("✅ LLM Ready")


# ==============================
# SYSTEM PROMPT
# ==============================
SYSTEM_PROMPT = """
You are a Senior System Architect.

Extract ONLY structured architecture from the text.

Rules:
- Return ONLY valid JSON
- No explanation
- No markdown
- No extra text

Extract:
- services
- databases
- apis
- message_queues
- relationships

Relationship format:
{"from": "", "to": "", "protocol": ""}

Output format:
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


# ==============================
# SAFE PARSER
# ==============================
def safe_parse(output):
    try:
        return json.loads(output)
    except:
        print("⚠️ Invalid JSON, skipping")
        return None


# ==============================
# MAIN FUNCTION
# ==============================
def extract_architecture(text_chunk: str) -> dict:
    """
    Uses llama.cpp to extract architecture
    """

    messages = BASE_MESSAGES + [
        {"role": "user", "content": text_chunk}
    ]

    response = llm.create_chat_completion(
        messages=messages,
        max_tokens=300,
        temperature=0.0,
        top_p=0.9,
        repeat_penalty=1.1
    )

    raw_output = response["choices"][0]["message"]["content"].strip()

    print("🧠 LLM RAW OUTPUT:")
    print(raw_output)

    parsed = safe_parse(raw_output)

    if not parsed:
        return {
            "services": [],
            "databases": [],
            "apis": [],
            "message_queues": [],
            "relationships": []
        }

    return parsed