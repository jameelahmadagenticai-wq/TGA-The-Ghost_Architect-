"""
TGA - Architect Manifesto Generator

Flow:
Architecture State -> LLM -> Markdown ADR

Output:
output/ARCHITECTS_MANIFESTO.md
"""

import json
import multiprocessing
from pathlib import Path

from llama_cpp import Llama


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "llm" / "model.gguf"
STATE_PATH = BASE_DIR / "output" / "architecture_state.json"
OUTPUT_PATH = BASE_DIR / "output" / "ARCHITECTS_MANIFESTO.md"

N_CTX = 4096
N_THREADS = multiprocessing.cpu_count()

llm = None


def get_llm():
    global llm

    if llm is None:
        print("Loading manifesto model...")
        llm = Llama(
            model_path=str(MODEL_PATH),
            n_ctx=N_CTX,
            n_threads=N_THREADS,
            verbose=False,
        )
        print("Manifesto model loaded")

    return llm


def load_state():
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt(state):
    return f"""
You are a Senior Software Architect.

Given the following system architecture in JSON, write a professional architectural document.

Architecture:
{json.dumps(state, indent=2)}

Write a structured Markdown document with:

# Overview
- High-level summary of the system

# Components
- Explain each service, database, API, and message queue

# Decisions & Rationale
- Why this architecture is chosen
- Why specific technologies are used
- Why relationships exist

# Open Questions
- What is unclear or needs further decisions

Rules:
- Be concise but professional
- No JSON output
- Only Markdown
"""


def generate_manifesto(state):
    model = get_llm()
    prompt = build_prompt(state)

    response = model.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are a senior system architect."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.3,
    )

    return response["choices"][0]["message"]["content"].strip()


def save_manifesto(text):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(text)

    print("Manifesto saved at:", OUTPUT_PATH)


if __name__ == "__main__":
    architecture_state = load_state()
    manifesto = generate_manifesto(architecture_state)
    save_manifesto(manifesto)
