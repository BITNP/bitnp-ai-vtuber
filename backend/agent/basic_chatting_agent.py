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
    def __init__(self, server_url: str, agent_name: str, llm_api_config: BotConfig, tts_config: TTS_Config):
        super().__init__(server_url, agent_name, llm_api_config)

        define_speaker(name=agent_name, **tts_config)

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

        self._curr_agent_response = ""

        self._curr_task: asyncio.Task = None

        @self.on("user_input")
        async def handle_user_input(_, timestamp: str, event_data: EventData):
            """
            Handle user input event
            """
            interrupted = False

            if self._curr_task:
                # print("[interrupted!]") # DEBUG
                interrupted = self.interrupt()

            self._curr_agent_response = ""

            async def task_func():
                content = event_data.get("content", "")

                if is_empty(content):
                    return
                
                if interrupted:
                    content = "(打断了你) " + content

                # 调用 LLM API 处理用户输入
                self.llm.append_context(content, "user")
                res = await self.llm.respond_to_context()
                # print(f"LLM 回复: {res}") # DEBUG

            task = asyncio.create_task(task_func())
            self._curr_task = task
        
        # @self.loop
        # async def test_loop(self: 'BasicChattingAgent'):
        #     print("test_loop")

        @self.llm.on("start_of_response")
        async def handle_start_of_response(data):
            await self.emit({"type": "start_of_response"})

        @self.llm.on("message_delta")
        async def handle_message_delta(data):
            await asyncio.sleep(0.1) # check point (to check if the conversation is interrupted)
            await self.sentence_sep_node.handle(data["content"])
        
        @self.llm.on("done")
        async def handle_done(data):
            self.llm.messages.append({"role": "assistant", "content": data["content"]})
            await self.sentence_sep_node.handle(" ")
            await self.emit({"type": "end_of_response", "response": data["content"]})
    
    def interrupt(self):
        """
        Interrupt the current task
        """
        should_interrupt = False

        if self._curr_task:
            self._curr_task.cancel()
            self._curr_task = None
            if len(self.llm.messages) > 0 and self.llm.messages[-1].get("role") != "assistant":
                self.llm.messages.insert(-1, {"role": "assistant", "content": f"{self._curr_agent_response}"})
                should_interrupt = True
            self.sentence_sep_node.reset()

        return should_interrupt
    
    async def generate_tts_base64(self, text: str):
        """
        Generate TTS base64 audio data
        """
        print("generating tts:", text)
        wav_data = await get_tts_wav(text=text, speaker_name=self.agent_name)
        # wav_data = b""
        # for chunk in wav_generator:
        #     if chunk:
        #         wav_data += chunk

        try:
            base64_wav_data = base64.b64encode(wav_data).decode("utf-8")
            return base64_wav_data
        except Exception as e:
            print(f"Error encoding wav to base64: {e}")
            return ""
        
    async def handle_event(self, data: dict):
        """
        Handle event
        """
        data_type = data.get("type", "")
        content = data.get("content", "")

        await asyncio.sleep(0) # check point (to check if the conversation is interrupted)

        if data_type == "text":
            self._curr_agent_response += content
            media_data = await self.generate_tts_base64(text=content)
            await self.emit({"type": "say_aloud", "content": content, "media_data": media_data})
        elif data_type == "tag":
            self._curr_agent_response += f"[{content}]"
            await self.emit({"type": "bracket_tag", "content": content})