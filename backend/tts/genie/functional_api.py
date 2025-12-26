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
    

    # # sync (Genie's sync api does not return wav data, it just saves to disk, which is fxxking retarded!)
    # genie.tts(
    #     character_name=speaker_name,
    #     text=text,
    #     play=False, # 不允许播放
    #     split_sentence=False,
    #     save_path='./temp.wav'
    # )
    # with open('./temp.wav', 'rb') as f:
    #     wav_data = f.read()
    # return wav_data

    # async (Genie / GPT-SoVITS does not support streaming! This is actually fake streaming.)
    iterator = genie.tts_async(
        character_name=speaker_name,
        text=text,
        play=False, # 不允许播放
        split_sentence=False,
        # save_path=None
    )

    audio_chunks = []
    async for chunk in iterator:
        audio_chunk = np.frombuffer(chunk, dtype=np.int16)
        audio_chunks.append(audio_chunk)

    combined_audio = np.concatenate(audio_chunks)

    sample_rate = 32000 # 32kHz
    target_silence_ms = 200 # 目标静音长度（毫秒）

    # 保证固定的静音时长
    if not audio_chunks:
        target_samples = int(sample_rate * target_silence_ms / 1000)
        final_audio = np.zeros(target_samples, dtype=np.int16)
    else:
        combined_audio = np.concatenate(audio_chunks)
        
        # 从后向前找到第一个非零值（简单静音检测）
        # 找到绝对值大于10的最后一个样本的位置
        non_silent_indices = np.where(np.abs(combined_audio) > 10)[0]
        
        if len(non_silent_indices) == 0:
            # 整个音频都是静音
            audio_end = 0
        else:
            audio_end = non_silent_indices[-1] + 1  # 最后一个有声音的索引+1
        
        # 计算需要添加的静音
        target_samples = int(sample_rate * target_silence_ms / 1000)
        current_samples_after_end = len(combined_audio) - audio_end
        
        if current_samples_after_end >= target_samples:
            # 如果已有足够静音，截取到音频结束+目标静音长度
            final_audio = combined_audio[:audio_end + target_samples]
        else:
            # 如果静音不足，添加静音
            samples_to_add = target_samples - current_samples_after_end
            silence_to_add = np.zeros(samples_to_add, dtype=np.int16)
            final_audio = np.concatenate([combined_audio[:audio_end + current_samples_after_end], silence_to_add])
    

    # 2. 创建WAV文件二进制数据
    # 使用BytesIO作为内存文件
    wav_bytesio = io.BytesIO()
    
    with wave.open(wav_bytesio, 'wb') as wav_file:
        # 设置WAV参数
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)   # 16位 = 2字节
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(final_audio.tobytes())

    wav_bytesio = wav_bytesio.getvalue()
    
    return wav_bytesio
