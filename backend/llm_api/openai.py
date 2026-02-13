from typing import List, Optional, Dict, Any
from .abstract_bot import AbstractBot

import json
import asyncio
import traceback
from openai import AsyncOpenAI

class OpenAIBot(AbstractBot):
    """
    A delegate used to communicate with OpenAI API
    """
    
    def __init__(self, token: str, model_name: Optional[str] = None, system_prompt: Optional[str] = None, max_context_length: int = 11, base_url: Optional[str] = None):
        super().__init__()
        
        self.token = token
        self.model_name = model_name or 'gpt-3.5-turbo'
        self.response = ''
        self.buffer = ''
        self.messages = []  # 在本地记录聊天记录
        self.system_prompt = system_prompt
        self.max_context_length = max_context_length
        self.base_url = base_url
        
        # 创建OpenAI客户端，支持自定义base_url
        client_kwargs = {'api_key': token}
        if base_url:
            client_kwargs['base_url'] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)

    async def setup(self):
        """do nothing..."""
        pass

    def append_context(self, text: str, role: str = 'user'):
        """Append context to messages"""
        self.messages.append({
            'role': role,
            'content': text,
        })

    async def respond_to_context(self, messages: Optional[List[Dict]] = None) -> str:
        """Send messages to OpenAI API and stream the response"""
        
        await self._dispatch_event('start_of_response')

        if not messages:
            messages = self.messages

        from pprint import pprint # DEBUG
        print("context:") # DEBUG
        pprint(messages) # DEBUG

        # 保留max_context_length条历史
        filtered_messages = messages[-self.max_context_length:] if len(messages) > self.max_context_length else messages.copy()
        
        if self.system_prompt:
            filtered_messages.insert(0, {
                'role': 'system',
                'content': self.system_prompt,
            })

        self.response = ''

        try:
            # 调用OpenAI API，使用流式响应
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=filtered_messages,
                stream=True
            )

            async for chunk in stream:
                delta_text = chunk.choices[0].delta.content or ''
                
                if not delta_text:
                    continue
                
                self.response += delta_text
                await self._dispatch_event('message_delta', {'content': delta_text})

        except Exception as error:
            traceback.print_exc()
            print(f'[OpenAIBot] Error: {error}')

        await self._dispatch_event('done', {'content': self.response})
        return self.response