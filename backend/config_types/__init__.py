# config classes
from pydantic import BaseModel, ConfigDict
from typing import Iterator, Tuple, Any, Union


class CompatibaleModel(BaseModel):
    """support dict-like access & extra fields"""

    model_config = ConfigDict(extra="allow")

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


class OmniVoice_TTS_Config(CompatibaleModel):
    """
    Config for OmniVoice TTS
    
    安装依赖:
        cd backend/tts/omnivoice
        uv venv .venv
        source .venv/bin/activate
        uv sync --extra cuda
        python download_model.py
    """

    tts_method_name: str = "omnivoice"
    model_path: str = "backend/tts/omnivoice/models/k2-fsa/OmniVoice"
    device: str = "auto"
    dtype: str = "float16"
    ref_audio: str | None = None
    ref_text: str | None = None


class Http_TTS_Config(CompatibaleModel):
    """
    Config for HTTP TTS (调用远程 OmniVoice 服务)
    
    使用方法:
        1. 在 omnivoice 虚拟环境中启动服务:
            cd backend/tts/omnivoice
            source .venv/bin/activate
            python tts_server.py --port 9237
        
        2. 配置 Http_TTS_Config
    """

    tts_method_name: str = "http"
    base_url: str = "http://127.0.0.1:9237"
    ref_audio: str | None = None
    ref_text: str | None = None


TTS_Config = Union[Genie_TTS_Config, Dashscope_TTS_Config, OmniVoice_TTS_Config, Http_TTS_Config]


class VLM_Config(CompatibaleModel):
    """
    Config for Vision Language Models (VLM)
    """

    provider: str
    api_key: str
    model_name: str = "glm-4v-flash"


class AgentConfig(CompatibaleModel):
    """
    Config for common agents
    """

    server_url: str
    agent_name: str
    llm_api_config: LLM_Config
    tts_stream: bool = False


class InteractiveLectureAgentConfig(CompatibaleModel):
    """
    Config for InteractiveLectureAgent
    
    支持背景图片、文字稿循环播放、语音识别打断、上下文压缩
    """

    agent_type: str = "interactive_lecture_agent"
    llm_api_config: LLM_Config
    tts_config: TTS_Config
    tts_stream: bool = False
    background_image: str | None = None
    system_prompt: str | None = None
    script_path: str | None = None
    context_compress_threshold: float = 0.5