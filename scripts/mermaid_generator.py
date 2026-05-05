"""
========================================
TGA - STEP 3.1 (MERMAID GENERATOR)
========================================

Flow:
State JSON → Mermaid Diagram

Replaceable Sections:
[NODE_FORMATTING]
[GRAPH_DIRECTION]
========================================
"""

import json
from pathlib import Path


# ========================================
# [CONFIG] 🔁
# ========================================
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "output" / "architecture_state.json"
GRAPH_DIRECTION = "TD"  # TD (top-down) or LR (left-right)


# ========================================
# [NODE FORMATTERS] 🔁
# ========================================
def format_service(name):
    key = name.replace(" ", "_").upper()
    label = name.title()
    return key, f'{key}[{label}]'


def format_database(name):
    key = name.replace(" ", "_").upper()
    label = name.title()
    return key, f'{key}[({label})]'


# ========================================
# LOAD STATE
# ========================================
def load_state():
    with open(STATE_PATH, "r") as f:
        return json.load(f)


# ========================================
# GENERATE MERMAID
# ========================================
def generate_mermaid(state):
    lines = []
    nodes = set()

    lines.append(f"graph {GRAPH_DIRECTION}")

    # ------------------------------------
    # SERVICES
    # ------------------------------------
    for svc in state.get("services", []):
        key, node = format_service(svc)
        nodes.add(key)
        lines.append(f"    {node}")

    # ------------------------------------
    # DATABASES
    # ------------------------------------
    for db in state.get("databases", []):
        key, node = format_database(db)
        nodes.add(key)
        lines.append(f"    {node}")

    # ------------------------------------
    # RELATIONSHIPS
    # ------------------------------------
    for rel in state.get("relationships", []):
        from_key = rel.get("from", "").replace(" ", "_").upper()
        to_key = rel.get("to", "").replace(" ", "_").upper()
        protocol = rel.get("protocol", "").upper()

        if not from_key or not to_key:
            continue

        if protocol:
            lines.append(f"    {from_key} -->|{protocol}| {to_key}")
        else:
            lines.append(f"    {from_key} --> {to_key}")

    return "\n".join(lines)


# ========================================
# MAIN
# ========================================
if __name__ == "__main__":
    state = load_state()
    mermaid_code = generate_mermaid(state)

    print("\n📊 Mermaid Diagram:\n")
    print(mermaid_code)
