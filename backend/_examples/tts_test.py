import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.api_silicon_functional import handle_define_speaker, get_tts_wav

# 定义 Speaker
handle_define_speaker(
        name="paimeng",
        gpt_weights_path="../tts/GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
        sovits_weights_path="../tts/GPT_SoVITS/pretrained_models/s2G488k.pth",
        ref_wav_path="../tts/ref_audio/paimeng.wav",
        prompt_text="蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。",
        prompt_language="zh")

# 调用 api (functional) 生成 wav 音频数据
wav_generator = get_tts_wav(text="你好呀，我是AI虚拟主播树莓娘", text_language="zh", spk="paimeng")

# 保存到音频文件
output_filename = "output.wav"
with open(output_filename, 'wb') as f:
   for chunk in wav_generator:
        if chunk:
            f.write(chunk)