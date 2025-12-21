import sys
import os
import io
import wave
import numpy as np
# from .tts import *
from config_types import TTS_Config


curr_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(curr_dir, "Genie-TTS", "src")) # use local Genie-TTS

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ["GENIE_DATA_DIR"] = os.path.join(curr_dir, "pretrained", "GenieData")
import genie_tts as genie

def is_nonsense(text: str):
    """
    Check if the text is nonsense
    """
    punctuation = ("，。！？、 \n,.!?\"'‘’“”：【】「」{}[]@#$%^&*()（）-=+——|｜\t\r\\"
                  "：；，。.！!？?\n.·、$./—-~…～…")
    # PUNCTUATION = ["!", "?", "…", ",", ".", "-"]
    # PUNCTUATION_REPLACEMENTS = {
    #     "：": ",", "；": ",", "，": ",", "。": ".", "！": "!",
    #     "？": "?", "\n": ".", "·": ",", "、": ",", "$": ".",
    #     "/": ",", "—": "-", "~": "…", "～": "…",
    # }
    return text.strip() == "" or all(c in punctuation for c in text.strip())

def define_speaker(name: str, onnx_model_dir: str, language: str, ref_audio_path: str, ref_audio_text: str, ref_audio_language: str):
    """
    Define a speaker with the given name and TTS config
    """
    genie.load_character(
        character_name=name,
        onnx_model_dir=onnx_model_dir,  # 包含 ONNX 模型的文件夹
        language=language,
    )
    genie.set_reference_audio(
        character_name=name,  # 必须与加载的角色名称匹配
        audio_path=ref_audio_path,  # 参考音频的路径
        audio_text=ref_audio_text,  # 对应的文本
        language=ref_audio_language
    )

async def get_tts_wav(text: str, speaker_name: str) -> bytes:
    """
    Generate TTS wav data for the given text, speaker name
    """
    if is_nonsense(text):
        return b""
    
    # iterator = genie.tts_async(
    #     character_name=speaker_name,
    #     text=text,
    #     play=False, # 不允许播放
    #     split_sentence=False,
    #     # save_path=None
    # )

    genie.tts(
        character_name=speaker_name,
        text=text,
        play=False, # 不允许播放
        split_sentence=False,
        save_path='./temp.wav'
    )

    # 1. 读取生成的WAV文件
    with open('./temp.wav', 'rb') as f:
        wav_data = f.read()

    # # breakpoint()

    # audio_chunks = []
    # async for chunk in iterator:
    #     audio_chunk = np.frombuffer(chunk, dtype=np.int16)
    #     audio_chunks.append(audio_chunk)

    # combined_audio = np.concatenate(audio_chunks)
    
    # # 2. 创建WAV文件二进制数据
    # # 使用BytesIO作为内存文件
    # wav_bytesio = io.BytesIO()
    # sample_rate = 32000 # 32kHz
    
    # with wave.open(wav_bytesio, 'wb') as wav_file:
    #     # 设置WAV参数
    #     wav_file.setnchannels(1)  # 单声道
    #     wav_file.setsampwidth(2)   # 16位 = 2字节
    #     wav_file.setframerate(sample_rate)
    #     wav_file.writeframes(combined_audio.tobytes())

    # wav_bytesio = wav_bytesio.getvalue()
    
    # return wav_bytesio
    return wav_data
