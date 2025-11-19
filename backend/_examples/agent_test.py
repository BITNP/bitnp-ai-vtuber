import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import BasicChattingAgent
from tokens import get_token
from pprint import pprint

bot_config = {
    'api_name': 'glm',
    'token': get_token('glm'),
    'model_name': 'glm-4-flash',
    'system_prompt': '你是树莓娘，网络开拓者协会的看板娘。', # 系统提示词
    'max_context_length': 11 # 最大上下文长度 (轮数)
}

agent = BasicChattingAgent(bot_config)