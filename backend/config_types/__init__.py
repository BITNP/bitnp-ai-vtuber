# config classes
from pydantic import BaseModel, ConfigDict
from typing import Iterator, Tuple, Any, Union

class CompatibaleModel(BaseModel):
    """support dict-like access & extra fields"""

    model_config = ConfigDict(extra='allow')

    def __iter__(self) -> Iterator[Tuple[str, Any]]:
        for field_name in self.model_fields:
            yield field_name, getattr(self, field_name)
    
    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"字段 '{key}' 不存在")
    
    def keys(self):
        return self.model_fields.keys()
    
    def values(self):
        return (getattr(self, field) for field in self.model_fields)
    
    def items(self):
        return ((field, getattr(self, field)) for field in self.model_fields)


class LLM_Config(CompatibaleModel):
    """
    Config for common LLM APIs
    """
    api_name: str
    token: str
    model_name: str
    system_prompt: str
    max_context_length: int

class Genie_TTS_Config(CompatibaleModel):
    """
    Config for Genie-TTS
    """
    tts_method_name: str = "genie"
    onnx_model_dir: str
    language: str
    ref_audio_path: str
    ref_audio_text: str
    ref_audio_language: str

class Dashscope_TTS_Config(CompatibaleModel):
    """
    Config for Dashscope TTS
    """
    tts_method_name: str = "dashscope"
    api_key: str
    model: str
    voice: str

TTS_Config = Union[Genie_TTS_Config, Dashscope_TTS_Config]

class AgentConfig(CompatibaleModel):
    """
    Config for common agents
    """
    server_url: str
    agent_name: str
    llm_api_config: LLM_Config
    tts_stream: bool = False
