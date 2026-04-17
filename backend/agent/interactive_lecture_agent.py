"""
Interactive Lecture Agent: 支持背景图片、文字稿循环播放、语音识别打断、上下文压缩
"""
from __future__ import annotations

from .abstract_agent import Agent, EventData

import asyncio
import base64
import io
import os
import sys
import urllib.parse
import wave
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tts import create_tts
from tts.pcm2wav import pcm2wav
from llm_api import create_bot

from config_types import LLM_Config, TTS_Config


def _ws_to_http(ws_url: str) -> str:
    if ws_url.startswith("wss://"):
        return ws_url.replace("wss://", "https://", 1)
    if ws_url.startswith("ws://"):
        return ws_url.replace("ws://", "http://", 1)
    if ws_url.startswith("https://") or ws_url.startswith("http://"):
        return ws_url
    return "http://" + ws_url


def _get_audio_duration(audio_data: bytes) -> float:
    """计算 WAV 音频时长（秒）"""
    try:
        with wave.open(io.BytesIO(audio_data), 'rb') as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return frames / rate if rate > 0 else 0
    except Exception:
        return 0


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
        ppt_base_url: str = "/documents/slides",
        auto_start: bool = True,
        **kwargs,
    ):
        super().__init__(server_url, agent_name)

        self.llm = create_bot(**llm_api_config)
        self.tts = create_tts(**tts_config)
        self.tts_stream = tts_stream
        self.auto_start = auto_start

        self.background_image = background_image
        self.system_prompt = system_prompt
        self.script_path = script_path
        self.context_compress_threshold = context_compress_threshold
        self.ppt_base_url = ppt_base_url.rstrip("/")

        self._scripts: List[str] = []
        self._curr_index: int = 0
        self._is_playing: bool = False
        self._is_paused_for_question: bool = False
        self._play_task: Optional[asyncio.Task] = None
        self._answer_task: Optional[asyncio.Task] = None
        self._initialized: bool = False

        self._load_scripts()

        self.loop(self._initialize_loop)

    async def _initialize_loop(self, _agent: "InteractiveLectureAgent"):
        """初始化循环，确保 initialize 只执行一次"""
        if self._initialized:
            return
        self._initialized = True
        await self.initialize()

    async def initialize(self):
        """初始化 Agent，发送初始事件"""
        if self.background_image:
            await self._emit_background_as_ppt()

        if self.auto_start and self._scripts:
            await self.start_playing()

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

    async def _emit_background_as_ppt(self):
        """将背景图片作为1页PPT发送"""
        if not self.background_image or not os.path.exists(self.background_image):
            return

        filename = os.path.basename(self.background_image)
        http_base = _ws_to_http(self.server_url)
        url = f"{http_base}{self.ppt_base_url}/{urllib.parse.quote(filename)}"

        await self.emit({
            "type": "ppt_assets",
            "urls": [url],
            "total": 1
        })

        await self.emit({
            "type": "flip_ppt_page",
            "page_num": 1
        })

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

        await self.emit({"type": "start_of_response"})
        await self._speak_response(response)
        await self.emit({"type": "end_of_response", "response": response})
        await self._check_and_compress_context()

    async def _speak_response(self, text: str):
        """播报回答"""
        try:
            if self.tts_stream:
                async for media_data in self.tts.synthesize_stream(text):
                    if self.tts.format == "pcm":
                        media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                    base64_data = base64.b64encode(media_data).decode("utf-8")
                    duration = _get_audio_duration(media_data)
                    await self.emit({
                        "type": "say_aloud",
                        "content": text,
                        "media_data": base64_data,
                        "format": "wav",
                        "is_last": True,
                        "duration": duration
                    })
            else:
                media_data = await self.tts.synthesize(text)
                if self.tts.format == "pcm":
                    media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                base64_data = base64.b64encode(media_data).decode("utf-8")
                duration = _get_audio_duration(media_data)
                await self.emit({
                    "type": "say_aloud",
                    "content": text,
                    "media_data": base64_data,
                    "format": "wav",
                    "is_last": True,
                    "duration": duration
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

        await self.emit({"type": "start_of_response"})

        try:
            if self.tts_stream:
                async for media_data in self.tts.synthesize_stream(script):
                    if self._is_paused_for_question or not self._is_playing:
                        break
                    
                    if self.tts.format == "pcm":
                        media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                    base64_data = base64.b64encode(media_data).decode("utf-8")
                    duration = _get_audio_duration(media_data)
                    
                    await self.emit({
                        "type": "say_aloud",
                        "content": script,
                        "media_data": base64_data,
                        "format": "wav",
                        "is_last": True,
                        "duration": duration
                    })
            else:
                media_data = await self.tts.synthesize(script)
                print(f"[DEBUG] TTS合成完成, media_data长度: {len(media_data) if media_data else 0}")
                if self.tts.format == "pcm":
                    media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                base64_data = base64.b64encode(media_data).decode("utf-8")
                duration = _get_audio_duration(media_data)
                print(f"[DEBUG] 发送 say_aloud, content长度: {len(script)}, duration: {duration}")
                
                await self.emit({
                    "type": "say_aloud",
                    "content": script,
                    "media_data": base64_data,
                    "format": "wav",
                    "is_last": True,
                    "duration": duration
                })
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"播放出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"[DEBUG] 发送 end_of_response, script长度: {len(script)}")
            await self.emit({"type": "end_of_response", "response": script})

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