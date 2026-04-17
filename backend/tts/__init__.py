import importlib.util
from .abstract_tts import AbstractTTS
from .genie import GenieTTS
from .dashscope import DashscopeTTS
from .http_tts import HttpTTS
from typing import Literal, Type

REGISTRY: dict[str, Type[AbstractTTS]] = {
    "genie": GenieTTS,
    "dashscope": DashscopeTTS,
    "http": HttpTTS,
}

Available_TTS_Methods = Literal["genie", "dashscope", "omnivoice", "http"]


def create_tts(tts_method_name: Available_TTS_Methods, **kwargs) -> AbstractTTS:
    """
    Create a TTS instance.
    
    Args:
        tts_method_name: TTS method name ("genie", "dashscope", "omnivoice")
        **kwargs: Additional arguments for the TTS constructor
        
    Returns:
        AbstractTTS: TTS instance
        
    Raises:
        ValueError: If TTS method not found
    """
    if tts_method_name == "omnivoice":
        from .omnivoice import OmniVoiceTTS
        return OmniVoiceTTS(**kwargs)
    
    if tts_method_name not in REGISTRY:
        raise ValueError(f"TTS {tts_method_name} not found. Available: {list(REGISTRY.keys())}")
    
    return REGISTRY[tts_method_name](**kwargs)


def get_available_tts() -> list[str]:
    """Get list of available TTS methods."""
    available = list(REGISTRY.keys())
    
    if importlib.util.find_spec("omnivoice") is not None:
        available.append("omnivoice")
    
    return available