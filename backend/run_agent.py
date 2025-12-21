import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
curr_dir = os.path.dirname(os.path.abspath(__file__))

from config_types import LLM_Config, TTS_Config, AgentConfig
from agent import create_agent
from tokens import get_token
from prompts import get_prompt

server_url = "localhost:8000"
agent_name = "shumeiniang"

llm_api_config = LLM_Config(
    api_name = 'glm',
    token = get_token('glm'),
    model_name = 'glm-4-flash',
    system_prompt = get_prompt('shumeiniang'), # 系统提示词
    max_context_length = 11 # 最大上下文长度 (轮数)
)

tts_config = TTS_Config(
    # onnx_model_dir = "./tts/pretrained/CharacterModels/v2ProPlus/mika/tts_models",
    # onnx_model_dir = "./tts/pretrained/CharacterModels/v2ProPlus/feibi/tts_models",
    # onnx_model_dir = "/Users/indexerror/Documents/MyStuff/Projects/Playground/Genie/test/onnx_output",

    onnx_model_dir = os.path.join(curr_dir, "tts/pretrained/IndexError/gptsovits-v2proplus-genie-onnx-export"),
    language = "hybrid-zh-en",
    ref_audio_path = os.path.join(curr_dir, "tts/ref_audio/paimeng.wav"),
    ref_audio_text = "蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。",

    # ref_audio_path = "./tts/pretrained/CharacterModels/v2ProPlus/feibi/prompt_wav/zh_vo_Main_Linaxita_2_1_10_26.wav",
    # ref_audio_text = "在此之前，请您务必继续享受旅居拉古娜的时光。",

    ref_audio_language = "zh"
)

agent_config = AgentConfig(
    server_url = server_url,
    agent_name = agent_name,
    llm_api_config = llm_api_config,
    tts_config = tts_config
)

agent = create_agent(agent_type = 'basic_chatting_agent', **agent_config.model_dump())

asyncio.run(agent.run())
