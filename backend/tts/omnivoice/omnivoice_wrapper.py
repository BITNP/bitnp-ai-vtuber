import os
from typing import Optional


class OmniVoiceTTS:
    """
    OmniVoice TTS wrapper for standalone usage.
    
    安装:
        uv sync --extra cuda
        python download_model.py
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        device: str = "auto",
        dtype: str = "float16",
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
    ):
        if model_path is None:
            model_path = os.path.join(os.path.dirname(__file__), "models", "OmniVoice")
        
        self.model_path = model_path
        self.device = device
        self.dtype = dtype
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        
        self.model = None
        self._is_initialized = False
        self.sample_rate = 24000

    def _parse_device(self) -> str:
        if self.device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda:0"
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    return "mps"
            except ImportError:
                pass
            return "cpu"
        return self.device

    async def _ensure_initialized(self):
        if self._is_initialized:
            return
        
        from omnivoice import OmniVoice
        
        device = self._parse_device()
        
        print(f"[OmniVoice] Loading model from: {self.model_path}")
        print(f"[OmniVoice] Device: {device}, Dtype: {self.dtype}")
        
        self.model = OmniVoice.from_pretrained(
            self.model_path,
            device_map=device,
            dtype=self.dtype
        )
        
        self._is_initialized = True
        print("[OmniVoice] Model loaded successfully")

    async def synthesize(self, text: str) -> bytes:
        await self._ensure_initialized()
        
        if not text or not text.strip():
            return b""
        
        generate_kwargs = {"text": text}
        
        if self.ref_audio and os.path.exists(self.ref_audio):
            generate_kwargs["ref_audio"] = self.ref_audio
            if self.ref_text:
                generate_kwargs["ref_text"] = self.ref_text
        
        audio_list = self.model.generate(**generate_kwargs)
        
        if not audio_list or len(audio_list) == 0:
            return b""
        
        import soundfile as sf
        import io
        
        buffer = io.BytesIO()
        sf.write(buffer, audio_list[0], self.sample_rate, format='WAV')
        
        buffer.seek(0)
        return buffer.read()

    async def synthesize_stream(self, text: str):
        raise NotImplementedError(
            "OmniVoice does not support streaming synthesis. "
            "Use synthesize() method instead."
        )