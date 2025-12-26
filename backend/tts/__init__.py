from .abstract_tts import AbstractTTS
from .genie import GenieTTS
from .dashscope import DashscopeTTS
from typing import Literal

REGISTRY = {
    "genie": GenieTTS,
    "dashscope": DashscopeTTS,
}

Available_TTS_Methods = Literal["genie", "dashscope"]

def create_tts(tts_method_name: Available_TTS_Methods, **kwargs) -> AbstractTTS:
    if tts_method_name not in REGISTRY:
        raise ValueError(f"TTS {tts_method_name} not found in registry")
    return REGISTRY[tts_method_name](**kwargs)
