from .abstract_vlm import AbstractVLM
from .glm_vision import GlmVisionModel
from .openai_vision import OpenAIVisionModel

REGISTRY = {
    "glm": GlmVisionModel,
    "openai": OpenAIVisionModel,
}


def create_vlm(provider: str, **kwargs) -> AbstractVLM:
    """
    Create a VLM instance by provider name.

    Args:
        provider: Provider name (e.g., "glm")
        **kwargs: Arguments passed to the VLM constructor

    Returns:
        An instance of AbstractVLM

    Raises:
        ValueError: If provider not found in registry
    """
    if provider not in REGISTRY:
        raise ValueError(
            f"VLM provider '{provider}' not found in registry. Available: {list(REGISTRY.keys())}"
        )
    return REGISTRY[provider](**kwargs)