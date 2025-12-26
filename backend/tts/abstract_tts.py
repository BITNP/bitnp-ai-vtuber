from abc import ABC, abstractmethod
from typing import TypeVar, Literal, AsyncGenerator

Format = TypeVar('Format', bound=Literal['wav', 'mp3', 'pcm'])

class AbstractTTS(ABC):
    """
    Abstract class for TTS service.
    """
    def __init__(self, format: Format, **kwargs):
        self.format = format

        if self.format == "pcm":
            self.sample_rate = kwargs.get("sample_rate", 24000)
            self.channels = kwargs.get("channels", 1)
            self.bits_per_sample = kwargs.get("bits_per_sample", 16)

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """
        Synthesize text to audio bytes.

        Args:
            text (str): Text to synthesize.

        Returns:
            bytes: Audio bytes.
        """
        pass
    
    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to audio bytes stream.

        Args:
            text (str): Text to synthesize.

        Yields:
            bytes: Audio bytes.
        """
        pass