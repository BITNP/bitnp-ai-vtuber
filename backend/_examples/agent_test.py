import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import BasicChattingAgent
from tokens import get_token
from pprint import pprint

server_url = "localhost:8000"
agent_name = "shumeiniang"

llm_api_config = {
    'api_name': 'glm',
    'token': get_token('glm'),
    'model_name': 'glm-4-flash',
    'system_prompt': '你是树莓娘，网络开拓者协会的看板娘。', # 系统提示词
    'max_context_length': 11 # 最大上下文长度 (轮数)
}

tts_config = {
    "gpt_weights_path": "../tts/GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
    "sovits_weights_path": "../tts/GPT_SoVITS/pretrained_models/s2G488k.pth",
    "ref_wav_path": "../tts/ref_audio/paimeng.wav",
    "prompt_text": "蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。",
    "prompt_language": "zh"
}

agent = BasicChattingAgent(server_url, agent_name, llm_api_config, tts_config)

asyncio.run(agent.run())
