"""
LLM prompt bank
"""
import os
import json

self_dir = os.path.dirname(__file__)

AVAILABLE_PROMPTS = [f[:-4] for f in os.listdir(self_dir) if f.endswith(".txt")]

def get_prompt(prompt_name: str) -> str:
    if prompt_name not in AVAILABLE_PROMPTS:
        raise ValueError(f"Prompt {prompt_name} not found")

    with open(os.path.join(self_dir, f"{prompt_name}.txt"), "r") as f:
        return f.read()
