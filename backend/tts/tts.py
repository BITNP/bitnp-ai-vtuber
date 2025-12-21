import asyncio
import os
import re
import sys

from uuid import uuid4 as uuid
from typing import Literal, Optional, Union

curr_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(curr_dir, "Genie-TTS", "src"))

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.environ["GENIE_DATA_DIR"] = os.path.join(curr_dir, "pretrained", "GenieData")
import genie_tts as genie

SupportedLanguage = Literal['zh', 'en', 'jp']


def split_language(text: str) -> list[dict[Literal['language', 'content'], str]]:
    """
    从文本中提取中文和英文部分，返回一个包含语言和内容的列表。

    ### 参数:
    text (str): 输入的文本，包含中文和英文混合。

    ### 返回:
    list[dict[Literal['language', 'content'], str]]: 一个列表，每个元素是一个字典，包含语言（'zh'或'en'）和对应的内容。
    """

    pattern_eng = re.compile(r"[a-zA-Z]+")
    split = re.split(pattern_eng, text)
    matches = pattern_eng.findall(text)

    assert len(matches) == len(split) - 1, "Mismatch between number of English matches and Chinese parts"

    result = []
    for i, part in enumerate(split):
        if part.strip():
            result.append({'language': 'zh', 'content': part})
        if i < len(matches):
            result.append({'language': 'en', 'content': matches[i]})

    return result

class Speaker:
    def __init__(self, onnx_model_dir: str, language: Union[SupportedLanguage, Literal['hybrid']],
                 ref_audio_path: str, ref_audio_text: str, ref_audio_language: SupportedLanguage):

        
        self.language = language

        cid = str(uuid()) # 重复概率极小, 暂不考虑重复问题
        # breakpoint()
        genie.load_character(
            character_name=cid,
            onnx_model_dir=onnx_model_dir,  # 包含 ONNX 模型的文件夹
            language=language,
        )
        self.character_id: str = cid
        genie.set_reference_audio(
            character_name=cid,  # 必须与加载的角色名称匹配
            audio_path=ref_audio_path,  # 参考音频的路径
            audio_text=ref_audio_text,  # 对应的文本
            language=ref_audio_language
        )
    
    async def tts(self, text, save_path: Optional[str] = None):
        """
        异步合成文本到语音。

        ### 参数:
        text (str): 要合成的文本。
        save_path (Optional[str]): 可选的保存路径，用于存储生成的音频文件。

        ### 返回:
        bytes: 合成的音频数据。
        """

        iterator = genie.tts_async(
            character_name=self.character_id,
            text=text,
            play=False, # 不允许播放
            split_sentence=False,
            save_path=save_path
        )

        data = b''
        print('start')
        async for chunk in iterator:
            print('got chunk with length', len(chunk))
            data += chunk
        
        return data

async def test():
    speaker = Speaker(
        onnx_model_dir=os.path.join(curr_dir, "pretrained", "CharacterModels/v2ProPlus/mika/tts_models"),
        language='hybrid-zh-en',
        ref_audio_path=os.path.join(curr_dir, "ref_audio/paimeng.wav"),
        ref_audio_text="蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。",
        ref_audio_language='zh'
    )

    data = await speaker.tts("你好，我是树莓娘！ Oh yeah, I can speak English!", os.path.join(curr_dir, "temp.wav"))
    print(len(data))


if __name__ == "__main__":
    asyncio.run(test())