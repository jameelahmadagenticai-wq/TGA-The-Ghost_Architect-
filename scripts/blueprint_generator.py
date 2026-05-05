"""
========================================
TGA - STEP 3.3 (BLUEPRINT GENERATOR)
========================================

Flow:
architecture_state.json → blueprint.json

Replaceable Sections:
[STACK_TYPE]
[FILE_TEMPLATES]
========================================
"""

import json
import os
from pathlib import Path


# ========================================
# [CONFIG] 🔁
# ========================================
BASE_DIR = Path(__file__).resolve().parent.parent
STATE_PATH = BASE_DIR / "output" / "architecture_state.json"
OUTPUT_PATH = BASE_DIR / "output" / "blueprint.json"

STACK_TYPE = "python"  # "python" or "node"


# ========================================
# [FILE TEMPLATES] 🔁
# ========================================
def get_service_files(service_name):
    if STACK_TYPE == "python":
        return {
            "main.py": f"# Entry point for {service_name}\nfrom fastapi import FastAPI\napp = FastAPI()\n",
            "requirements.txt": "fastapi\nuvicorn\n",
            "Dockerfile": "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]\n",
            "README.md": f"# {service_name}\nService description.\n"
        }

    elif STACK_TYPE == "node":
        return {
            "index.js": f"// Entry point for {service_name}\n",
            "package.json": "{ \"name\": \"" + service_name + "\" }",
            "Dockerfile": "FROM node:18\nWORKDIR /app\nCOPY . .\nRUN npm install\nCMD [\"node\", \"index.js\"]\n",
            "README.md": f"# {service_name}\nService description.\n"
        }


# ========================================
# ROOT FILES
# ========================================
def get_root_files():
    return {
        "docker-compose.yml": "# Define your services here\n",
        ".env.example": "# Environment variables\n",
        ".gitignore": "__pycache__/\nnode_modules/\n.env\n"
    }


# ========================================
# LOAD STATE
# ========================================
def load_state():
    with open(STATE_PATH, "r") as f:
        return json.load(f)


# ========================================
# GENERATE BLUEPRINT
# ========================================
def generate_blueprint(state):
    blueprint = {}

    services = state.get("services", [])

    for svc in services:
        folder_name = svc.replace(" ", "-")
        blueprint[folder_name] = get_service_files(folder_name)

    # Add root files
    blueprint.update(get_root_files())

    return blueprint


# ========================================
# SAVE BLUEPRINT
# ========================================
def save_blueprint(blueprint):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(blueprint, f, indent=2)

    print("💾 Blueprint saved at:", OUTPUT_PATH)


# ========================================
# MAIN
# ========================================
if __name__ == "__main__":
    state = load_state()
    blueprint = generate_blueprint(state)
    save_blueprint(blueprint)
