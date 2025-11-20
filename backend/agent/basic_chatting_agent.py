"""
Basic chatting agent
"""
from .abstract_agent import Agent, BotConfig, EventData

import base64
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from stream_node import SentenceSepNode, BracketsParsorNode, LambdaNode
from tts import define_speaker, get_tts_wav
from typing import TypedDict

TTS_Config = TypedDict("TTS_Config", {
    "gpt_weights_path": str,
    "sovits_weights_path": str,
    "ref_wav_path": str,
    "prompt_text": str,
    "prompt_language": str,
})

def is_empty(content: str) -> bool:
    return not content.strip()

class BasicChattingAgent(Agent):
    def __init__(self, server_url: str, agent_name: str, llm_api_config: BotConfig = None, tts_config: TTS_Config = None):
        super().__init__(server_url, agent_name, llm_api_config)
        
        tts_config["name"] = agent_name
        define_speaker(**tts_config)

        # streaming workflow: sentence_sep -> brackets_parsor -> event_emitter
        self.sentence_sep_node = SentenceSepNode()
        self.brackets_parsor_node = BracketsParsorNode()

        async def event_emitter_lambda(_, data):
            await self.handle_event(data)

        self.event_emitter = LambdaNode(event_emitter_lambda)

        self.sentence_sep_node.connect_to(self.brackets_parsor_node)
        self.brackets_parsor_node.connect_to(self.event_emitter)

        # self.sentence_sep_node.connect_to(LambdaNode(lambda _, data: print("sentence_sep:", data, flush=True))) # DEBUG
        # self.brackets_parsor_node.connect_to(LambdaNode(lambda _, data: print("brackets_parsor:", data, flush=True))) # DEBUG
        # self.event_emitter.connect_to(LambdaNode(lambda _, data: print("event_emitter:", data, flush=True))) # DEBUG

        self._curr_task: asyncio.Task = None

        @self.on("user_input")
        async def handle_user_input(_, timestamp: str, event_data: EventData):
            """
            Handle user input event
            """

            if self._curr_task:
                print("[interrupted!]")
                self._curr_task.cancel()

            async def task_func():
                content = event_data.get("content", "")

                if is_empty(content):
                    return
                
                # 调用 LLM API 处理用户输入
                self.llm.append_context(content, "user")
                res_task = asyncio.create_task(self.llm.respond_to_context())
            # print(f"LLM 回复: {res}") # DEBUG

            print("creating task")
            task = asyncio.create_task(task_func())
            self._curr_task = task
        
        @self.loop
        async def test_loop(self: 'BasicChattingAgent'):
            print("test_loop")

        @self.llm.on("message_delta")
        async def handle_message_delta(data):
            await self.sentence_sep_node.handle(data["content"])
        
        @self.llm.on("done")
        async def handle_done(data):
            await self.sentence_sep_node.handle(" ")
    
    async def generate_tts_base64(self, text: str, text_language: str):
        """
        Generate TTS base64 audio data
        """
        print("generating tts:", text)
        wav_generator = get_tts_wav(text=text, text_language=text_language, spk=self.agent_name)
        wav_data = b""
        for chunk in wav_generator:
            if chunk:
                wav_data += chunk
        base64_wav_data = base64.b64encode(wav_data).decode("utf-8")
        return base64_wav_data
        
    async def handle_event(self, data: dict):
        """
        Handle event
        """
        data_type = data.get("type", "")
        content = data.get("content", "")

        await asyncio.sleep(0) # check point (to check if the conversation is interrupted)

        if data_type == "text":
            media_data = await self.generate_tts_base64(text=content, text_language="zh")
            await self.emit({"type": "say_aloud", "content": content, "media_data": media_data})
        elif data_type == "tag":
            await self.emit({"type": "bracket_tag", "content": content})