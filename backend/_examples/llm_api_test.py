import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_api import create_bot
from tokens import get_token
from pprint import pprint

bot_config = {
    'api_name': 'glm',
    'token': get_token('glm'),
    'model_name': 'glm-4-flash',
    'system_prompt': '你是树莓娘，网络开拓者协会的看板娘。', # 系统提示词
    'max_context_length': 11 # 最大上下文长度 (轮数)
}

bot = create_bot(**bot_config)

# 使用装饰器 @bot.on 来注册事件处理函数
# 同一个事件允许注册多个不同处理函数
# 每个处理函数可以是同步的也可以是异步的
@bot.on('message_delta')
async def handle_message_delta(data: dict):
    print(data['content'], end="", flush=True)
    # await asyncio.sleep(0.1)

@bot.on('done')
def handle_done(data: dict):
    print()

async def main():
    while True:
        user_input = input('用户: (请输入内容，输入exit退出) ')
        if user_input == 'exit':
            break
        bot.append_context(user_input, role='user')
        print('树莓娘: ', end="", flush=True)
        agent_response = await bot.respond_to_context()
        bot.append_context(agent_response, role='assistant')

        print('当前对话历史:')
        pprint(bot.messages)

if __name__ == '__main__':
    asyncio.run(main())


