from .abstract_bot import AbstractBot
from .glm import GlmBot
from .openai import OpenAIBot

REGISTRY = {
    "glm": GlmBot,
    "openai": OpenAIBot,
}

def create_bot(api_name: str, **kwargs) -> AbstractBot:
    if api_name not in REGISTRY:
        raise ValueError(f"Bot {api_name} not found in registry")
    return REGISTRY[api_name](**kwargs)