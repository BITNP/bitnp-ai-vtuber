"""
LLM API token gateway
"""
import os
import json

self_dir = os.path.dirname(__file__)

try:
    with open(os.path.join(self_dir, "tokens.json"), "r") as f:
        TOKENS: dict[str, str] = json.load(f)
except FileNotFoundError:
    with open(os.path.join(self_dir, "tokens.json"), "w") as f:
        json.dump({}, f)
    print(f"[Warning] tokens.json not found, empty json file created at {os.path.abspath(os.path.join(self_dir, 'tokens.json'))}")
    TOKENS: dict[str, str] = {}

def get_token(token_name: str) -> str:
    return TOKENS.get(token_name, "")