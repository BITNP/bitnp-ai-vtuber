from typing import List, Optional, Dict, Any
from sseclient import SSEClient
from .abstract_bot import AbstractBot

import json
import requests
import asyncio
import traceback

class GlmBot(AbstractBot):
    """
    A delegate used to communicate with GLM-4 api
    """
    
    def __init__(self, token: str, model_name: Optional[str] = None, system_prompt: Optional[str] = None, max_context_length: int = 11):
        super().__init__()
        
        self.token = token
        self.model_name = model_name or 'glm-4-flash'
        self.response = ''
        self.buffer = ''
        self.messages = []  # 在本地记录聊天记录
        self.system_prompt = system_prompt
        self.max_context_length = max_context_length

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
        """Send messages to GLM-4 API and stream the response"""
        
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

        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',  # 认证令牌
        }

        data = {
            'model': self.model_name,
            'messages': filtered_messages,
            'stream': True
        }

        self.response = ''

        try:
            response = requests.post(url, headers=headers, json=data, stream=True)
            response.raise_for_status()

            # 使用SSE客户端处理服务器发送事件
            client = SSEClient(response)
            
            for event in client.events():
                if event.data == '[DONE]':
                    await self._dispatch_event('done', {'content': self.response})
                    return self.response
                
                else:
                    try:
                        event_data = json.loads(event.data)
                        delta_text = event_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        
                        if not delta_text or delta_text == 'undefined':
                            continue
                        
                        self.response += delta_text
                        await self._dispatch_event('message_delta', {'content': delta_text})
                        
                    except json.JSONDecodeError as e:
                        print(f'[GlmBot] An error occurred when parsing event data: {e}')
                        continue

        except requests.exceptions.RequestException as error:
            print(f'[GlmBot] Error sending message: {error}')
        except Exception as error:
            traceback.print_exc()
            print(f'[GlmBot] Unexpected error: {error}')

        await self._dispatch_event('done', {'content': self.response})
        return self.response
