import asyncio
import json
import threading
import dashscope  # DashScope Python SDK 版本需要不低于1.23.9
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat, ResultCallback
from ..abstract_tts import AbstractTTS
from typing import AsyncGenerator, Tuple, List

# 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
# 若没有配置环境变量，请在初始化时传入API Key

# 以下为北京地域url，若使用新加坡地域的模型，需将url替换为：wss://dashscope-intl.aliyuncs.com/api-ws/v1/inference
dashscope.base_websocket_api_url='wss://dashscope.aliyuncs.com/api-ws/v1/inference'

# 模型
# 不同模型版本需要使用对应版本的音色：
# cosyvoice-v3-flash/cosyvoice-v3-plus：使用longanyang等音色。
# cosyvoice-v2：使用longxiaochun_v2等音色。
# 每个音色支持的语言不同，合成日语、韩语等非中文语言时，需选择支持对应语言的音色。详见CosyVoice音色列表。
DEFAULT_TARGET_MODEL = "cosyvoice-v3.5-flash"

def is_nonsense(text: str):
    """
    Check if the text is nonsense
    """
    punctuation = ("，。！？、 \n,.!?\"'‘’“”：【】「」{}[]@#$%^&*()（）-=+——|｜\t\r\\"
                  "：；，。.！!？?\n.·、$./—-~…～…")
    return text.strip() == "" or all(c in punctuation for c in text.strip())

# def get_timestamp():
#     now = datetime.now()
#     formatted_timestamp = now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
#     return formatted_timestamp

# 定义回调接口
class Callback(ResultCallback):
    def __init__(self):
        self.audio_chunks = []
        self.word_timestamps = {}
        self._complete_event = threading.Event()

    def on_event(self, message):
        json_data = json.loads(message)
        if json_data['payload'] and json_data['payload']['output'] and json_data['payload']['output']['sentence']:
            sentence = json_data['payload']['output']['sentence']
            words = sentence.get('words', [])
            if words:
                for word in words:
                    self.word_timestamps[word['begin_index']] = word

    def on_data(self, data: bytes) -> None:
        self.audio_chunks.append(data)

    def on_complete(self):
        self._complete_event.set()

    async def wait_for_complete(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._complete_event.wait)



class CosyVoiceTTS(AbstractTTS):
    """
    CosyVoice TTS
    """

    def __init__(self, api_key: str, voice: str, model: str = DEFAULT_TARGET_MODEL):
        super().__init__(format='wav', sample_rate=24000, channels=1, bits_per_sample=16)
        
        self.api_key = api_key
        self.voice = voice
        self.model = model
    
    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        生成语音数据的异步生成器
        
        Args:
            text: 要合成的文本
            
        Yields:
            bytes: WAV音频数据块
        """
        # TODO
        raise NotImplementedError

    async def synthesize(self, text: str, word_timestamp_enabled: bool = False) -> Tuple[bytes, List]:
        dashscope.api_key = self.api_key

        if word_timestamp_enabled:
            if is_nonsense(text):
                return b'', []

            callback = Callback()
            synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice,
                callback=callback,
                format=AudioFormat.WAV_24000HZ_MONO_16BIT,
                additional_params={'word_timestamp_enabled': True} if word_timestamp_enabled else None
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, synthesizer.call, text)

            await callback.wait_for_complete()

            audio = b''.join(callback.audio_chunks)
            timestamp_data = list(callback.word_timestamps.values())

            

            return audio, timestamp_data

        else:
            # without word timestamp
            print("DEBUG synthesize without word timestamp:", text)

            if is_nonsense(text):
                return b''

            synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=self.voice,
                format=AudioFormat.WAV_24000HZ_MONO_16BIT
            )
            audio = synthesizer.call(text)

            return audio
