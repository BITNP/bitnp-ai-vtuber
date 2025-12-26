from ..abstract_tts import AbstractTTS
from .functional_api import define_speaker, get_tts_wav
from uuid import uuid4 as uuid

class GenieTTS(AbstractTTS):
    def __init__(self, onnx_model_dir: str, language: str, ref_audio_path: str, ref_audio_text: str, ref_audio_language: str):
        super().__init__(format="wav")

        self.speaker_name = str(uuid())

        define_speaker(
            self.speaker_name,
            onnx_model_dir,
            language,
            ref_audio_path,
            ref_audio_text,
            ref_audio_language,
        )

    def synthesize(self, text: str) -> bytes:
        return get_tts_wav(text, self.speaker_name)
    
    def synthesize_stream(self, text: str):
        raise NotImplementedError('GenieTTS does not support streaming synthesis!')
