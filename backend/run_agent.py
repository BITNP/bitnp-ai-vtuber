import sys
import os
import asyncio
import argparse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
curr_dir = os.path.dirname(os.path.abspath(__file__))

from config_types import LLM_Config, OmniVoice_TTS_Config, Http_TTS_Config, AgentConfig
from agent import create_agent
from tokens import get_token
from prompts import get_prompt

parser = argparse.ArgumentParser(description="BITNP AI VTuber agent runner")
parser.add_argument("--server-url", default="localhost:8000", help="server url, e.g. localhost:8000")
parser.add_argument("--agent-name", default="shumeiniang", help="agent name")
parser.add_argument("--agent-type", default="basic_chatting_agent", choices=["basic_chatting_agent", "lecture_agent", "interactive_lecture_agent"], help="agent type")
parser.add_argument("--lecture-script", default=None, help="path to *_scripts.txt or generated_scripts directory")
parser.add_argument("--ppt-images-dir", default=None, help="ppt images directory for lecture_agent")
parser.add_argument("--ppt-base-url", default="/documents/slides", help="ppt assets base url on server")
parser.add_argument("--tts-stream", action="store_true", help="enable tts stream")
parser.add_argument("--no-tts-stream", action="store_true", help="disable tts stream")
parser.add_argument("--no-auto-start", action="store_true", help="disable auto start for lecture_agent")
parser.add_argument("--background-image", default=None, help="background image path for interactive_lecture_agent")
parser.add_argument("--system-prompt", default=None, help="system prompt for interactive_lecture_agent")
parser.add_argument("--context-compress-threshold", type=float, default=0.5, help="context compress threshold (0.0-1.0)")

args = parser.parse_args()

server_url = args.server_url
agent_name = args.agent_name

llm_api_config = LLM_Config(
    api_name = 'glm',
    token = get_token('glm'),
    model_name = 'glm-4-flash',
    system_prompt = get_prompt('antifraud'), # 系统提示词
    max_context_length = 11 # 最大上下文长度 (轮数)
)

tts_config = Http_TTS_Config(
    base_url = "http://127.0.0.1:9237",
    ref_audio = os.path.join(curr_dir, "tts/ref_audio/paimeng.wav"),
    ref_text = "蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。"
)
tts_stream = False

#tts_config = OmniVoice_TTS_Config(
#    model_path = os.path.join(curr_dir, "tts/omnivoice/models/k2-fsa/OmniVoice"),
#    device = "cuda:0",
#    dtype = "float16",
#    ref_audio = os.path.join(curr_dir, "tts/ref_audio/paimeng.wav"),
#    ref_text = "蒙德有很多风车呢。回答正确！蒙德四季风吹不断，所以水源的供应也很稳定。"
#)
#tts_stream = False

if args.agent_type == "lecture_agent":
    agent = create_agent(
        agent_type = "lecture_agent",
        server_url = server_url,
        agent_name = agent_name,
        llm_api_config = None,
        tts_config = tts_config,
        tts_stream = tts_stream,
        lecture_script_path = args.lecture_script,
        ppt_images_dir = args.ppt_images_dir,
        ppt_base_url = args.ppt_base_url,
        auto_start = not args.no_auto_start,
    )
elif args.agent_type == "interactive_lecture_agent":
    agent = create_agent(
        agent_type = "interactive_lecture_agent",
        server_url = server_url,
        agent_name = agent_name,
        llm_api_config = llm_api_config,
        tts_config = tts_config,
        tts_stream = tts_stream,
        background_image = args.background_image,
        system_prompt = args.system_prompt,
        script_path = args.lecture_script,
        context_compress_threshold = args.context_compress_threshold,
        ppt_base_url = args.ppt_base_url,
        auto_start = not args.no_auto_start,
    )
else:
    agent_config = AgentConfig(
        server_url = server_url,
        agent_name = agent_name,
        llm_api_config = llm_api_config,
        tts_config = tts_config,
        tts_stream = tts_stream,
    )
    agent = create_agent(agent_type = 'basic_chatting_agent', **agent_config.model_dump())

asyncio.run(agent.run())