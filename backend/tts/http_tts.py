"""
HTTP TTS - 调用远程 OmniVoice TTS 服务
"""
import aiohttp
import asyncio
from typing import Optional, AsyncGenerator
from tts.abstract_tts import AbstractTTS


class HttpTTS(AbstractTTS):
    """
    HTTP TTS，调用远程 OmniVoice TTS 服务
    
    用法:
        在 omnivoice 虚拟环境中启动服务:
            cd backend/tts/omnivoice
            source .venv/bin/activate
            python tts_server.py --port 9237
        
        然后配置:
            tts_config = Http_TTS_Config(
                base_url="http://127.0.0.1:9237",
                ref_audio="path/to/ref.wav",
                ref_text="参考文本"
            )
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:9237",
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
    ):
        super().__init__(format='wav', sample_rate=24000, channels=1, bits_per_sample=16)
        self.base_url = base_url.rstrip("/")
        self.ref_audio = ref_audio
        self.ref_text = ref_text

    async def synthesize(self, text: str) -> bytes:
        """同步合成（实际是调用远程服务）"""
        if not text or not text.strip():
            return b""

        url = f"{self.base_url}/synthesize"

        payload = {"text": text}
        if self.ref_audio:
            payload["ref_audio"] = self.ref_audio
        if self.ref_text:
            payload["ref_text"] = self.ref_text

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status != 200:
                        error = await response.text()
                        raise Exception(f"TTS request failed: {error}")
                    return await response.read()
        except Exception as e:
            raise Exception(f"TTS synthesis error: {e}")

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """流式合成（HTTP 不支持流式，返回完整音频）"""
        audio = await self.synthesize(text)
        if audio:
            yield audio