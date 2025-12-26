import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.dashscope.dashscope_tts import DashscopeTTS
from tokens import get_token
import asyncio
import wave
import struct

def save_pcm_as_wav(pcm_data: bytes, filename: str, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2):
    """
    将PCM数据保存为WAV文件
    
    Args:
        pcm_data: PCM音频数据
        filename: 输出文件名
        sample_rate: 采样率 (默认24000Hz)
        channels: 声道数 (默认1=单声道)
        sample_width: 采样位宽(字节) (默认2=16位)
    """
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    print(f"WAV文件已保存: {filename} (大小: {len(pcm_data)} 字节)")


async def main():
    dashscope_tts = DashscopeTTS(api_key=get_token('dashscope'), voice='qwen-tts-vc-guanyu-voice-20251225231327803-5cc2')

    data = await dashscope_tts.synthesize('你好，我是树莓娘')
    save_pcm_as_wav(data, 'test.wav')

if __name__ == '__main__':
    asyncio.run(main())
