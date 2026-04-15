"""
Interactive Lecture Agent: 支持背景图片、文字稿循环播放、语音识别打断、上下文压缩
"""
from __future__ import annotations

from .abstract_agent import Agent, EventData

import asyncio
import base64
import os
import sys
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tts import create_tts
from tts.pcm2wav import pcm2wav
from llm_api import create_bot

from config_types import LLM_Config, TTS_Config


class InteractiveLectureAgent(Agent):
    def __init__(
        self,
        server_url: str,
        agent_name: str,
        llm_api_config: LLM_Config,
        tts_config: TTS_Config,
        tts_stream: bool = False,
        background_image: str | None = None,
        system_prompt: str | None = None,
        script_path: str | None = None,
        context_compress_threshold: float = 0.5,
        **kwargs,
    ):
        super().__init__(server_url, agent_name)

        self.llm = create_bot(**llm_api_config)
        self.tts = create_tts(**tts_config)
        self.tts_stream = tts_stream

        self.background_image = background_image
        self.system_prompt = system_prompt
        self.script_path = script_path
        self.context_compress_threshold = context_compress_threshold

        self._scripts: List[str] = []
        self._curr_index: int = 0
        self._is_playing: bool = False
        self._is_paused_for_question: bool = False
        self._play_task: Optional[asyncio.Task] = None
        self._answer_task: Optional[asyncio.Task] = None

        self._load_scripts()

    async def initialize(self):
        """初始化 Agent，发送初始事件"""
        if self.background_image:
            await self.emit({
                "type": "show_background_image",
                "image": self.background_image
            })

        @self.on("user_input")
        async def handle_user_input(_, timestamp: str, event_data: EventData):
            content = event_data.get("content", "")
            await self.handle_user_question(content)

        @self.on("asr_result")
        async def handle_asr_result(_, timestamp: str, event_data: EventData):
            text = event_data.get("text", "")
            is_speech = event_data.get("is_speech", False)
            await self.handle_asr(text, is_speech)

        @self.on("question_detected")
        async def handle_question_detected(_, timestamp: str, event_data: EventData):
            question = event_data.get("question", "")
            await self.handle_user_question(question)

        @self.on("lecture_control")
        async def handle_lecture_control(_, timestamp: str, event_data: EventData):
            action = event_data.get("action", "")
            if action == "start":
                await self.start_playing()
            elif action == "pause":
                self.pause_playing()
            elif action == "resume":
                await self.resume_playing()
            elif action == "next":
                self.next_script()
            elif action == "prev":
                self.prev_script()

    def _load_scripts(self):
        """加载文字稿"""
        if not self.script_path or not os.path.exists(self.script_path):
            return

        if os.path.isdir(self.script_path):
            for filename in sorted(os.listdir(self.script_path)):
                if filename.endswith('.txt'):
                    filepath = os.path.join(self.script_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self._scripts.append(f.read())
        else:
            with open(self.script_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self._scripts = [s.strip() for s in content.split('\n\n') if s.strip()]

    async def handle_asr(self, text: str, is_speech: bool):
        """处理语音识别结果"""
        if is_speech and text:
            await self.pause_for_question()
            await self.emit({
                "type": "speech_detected",
                "text": text
            })

    async def handle_user_question(self, question: str):
        """处理用户问题"""
        if not question or self._is_paused_for_question:
            return

        await self.pause_for_question()

        await self.answer_question(question)

        await self.resume_playing()

    async def pause_for_question(self):
        """暂停播放以回答问题"""
        self._is_paused_for_question = True
        
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()
            try:
                await self._play_task
            except asyncio.CancelledError:
                pass

        await self.emit({
            "type": "paused_for_question"
        })

    async def answer_question(self, question: str):
        """回答用户问题"""
        await self.emit({
            "type": "answering_question",
            "question": question
        })

        if self.system_prompt:
            self.llm.append_context(f"角色设定: {self.system_prompt}", "system")
        
        self.llm.append_context(question, "user")

        response = await self.llm.respond_to_context()
        self.llm.append_context(response, "assistant")

        await self._speak_response(response)
        await self._check_and_compress_context()

    async def _speak_response(self, text: str):
        """播报回答"""
        try:
            if self.tts_stream:
                async for media_data in self.tts.synthesize_stream(text):
                    if self.tts.format == "pcm":
                        media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                    base64_data = base64.b64encode(media_data).decode("utf-8")
                    await self.emit({
                        "type": "say_aloud",
                        "content": text,
                        "media_data": base64_data,
                        "format": "wav"
                    })
            else:
                media_data = await self.tts.synthesize(text)
                if self.tts.format == "pcm":
                    media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                base64_data = base64.b64encode(media_data).decode("utf-8")
                await self.emit({
                    "type": "say_aloud",
                    "content": text,
                    "media_data": base64_data,
                    "format": "wav"
                })
        except Exception as e:
            print(f"TTS合成出错: {e}")

    def _calculate_context_ratio(self) -> float:
        """计算当前上下文占用比例"""
        if not hasattr(self.llm, 'max_context_length'):
            return 0.0
        
        max_length = self.llm.max_context_length
        if max_length <= 0:
            return 0.0
        
        current_length = len(str(self.llm.messages))
        return current_length / max_length

    async def _check_and_compress_context(self):
        """检查并压缩上下文"""
        ratio = self._calculate_context_ratio()
        
        if ratio > self.context_compress_threshold:
            await self._compress_context()

    async def _compress_context(self):
        """压缩上下文，保留系统提示和最近的消息"""
        if not hasattr(self.llm, 'messages') or len(self.llm.messages) <= 2:
            return

        system_messages = [m for m in self.llm.messages if m.get("role") == "system"]
        other_messages = [m for m in self.llm.messages if m.get("role") != "system"]

        keep_count = min(6, len(other_messages))
        compressed_messages = system_messages + other_messages[-keep_count:]

        self.llm.messages = compressed_messages

        await self.emit({
            "type": "context_compressed",
            "message_count": len(self.llm.messages)
        })

    async def start_playing(self):
        """开始播放文字稿"""
        if not self._scripts:
            return
        
        self._is_playing = True
        self._is_paused_for_question = False
        
        await self.emit({
            "type": "script_started",
            "total": len(self._scripts),
            "current": self._curr_index + 1
        })

        while self._is_playing:
            if self._curr_index >= len(self._scripts):
                self._curr_index = 0

            script = self._scripts[self._curr_index]
            await self._play_script(script)

            self._curr_index += 1

            await asyncio.sleep(0.5)

    async def _play_script(self, script: str):
        """播放单段文字稿"""
        await self.emit({
            "type": "script_changed",
            "index": self._curr_index,
            "content": script[:100]
        })

        try:
            if self.tts_stream:
                async for media_data in self.tts.synthesize_stream(script):
                    if self._is_paused_for_question or not self._is_playing:
                        break
                    
                    if self.tts.format == "pcm":
                        media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                    base64_data = base64.b64encode(media_data).decode("utf-8")
                    
                    await self.emit({
                        "type": "say_aloud",
                        "content": script,
                        "media_data": base64_data,
                        "format": "wav"
                    })
            else:
                media_data = await self.tts.synthesize(script)
                if self.tts.format == "pcm":
                    media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                base64_data = base64.b64encode(media_data).decode("utf-8")
                
                await self.emit({
                    "type": "say_aloud",
                    "content": script,
                    "media_data": base64_data,
                    "format": "wav"
                })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"播放出错: {e}")

    def pause_playing(self):
        """暂停播放"""
        self._is_playing = False
        if self._play_task and not self._play_task.done():
            self._play_task.cancel()

    async def resume_playing(self):
        """恢复播放"""
        self._is_paused_for_question = False
        if not self._is_playing:
            self._is_playing = True
            self._play_task = asyncio.create_task(self.start_playing())

    def next_script(self):
        """下一段文字稿"""
        if self._scripts:
            self._curr_index = (self._curr_index + 1) % len(self._scripts)

    def prev_script(self):
        """上一段文字稿"""
        if self._scripts:
            self._curr_index = (self._curr_index - 1) % len(self._scripts)