"""
online teacher agent
"""
from .abstract_agent import Agent, EventData

import base64
import asyncio
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from stream_node import SentenceSepNode, BracketsParsorNode, LambdaNode
from llm_api import create_bot
from tts import create_tts
from tts.pcm2wav import pcm2wav

from config_types import LLM_Config, TTS_Config

def is_empty(content: str) -> bool:
    return not content.strip()

class OnlineTeacherAgent(Agent):
    def __init__(self, server_url: str, agent_name: str, llm_api_config: LLM_Config, tts_config: TTS_Config, command_json_path: str, tts_stream: bool = False):
        super().__init__(server_url, agent_name)

        self.llm_api_config = llm_api_config
        self.tts = create_tts(**tts_config)

        self.tts_stream = tts_stream
        self.command_json_path = command_json_path
        self.commands = []
        self.interaction_commands = []
        self.current_command_index = 0
        self.is_playing = False
        self.is_interaction = False
        self.interaction_prompt = ""
        self.interaction_duration = 0
        self.first_sentence_emitted = False
        self.response_done = False  # 标记LLM回复是否已完成

        # streaming workflow: sentence_sep -> brackets_parsor -> event_emitter
        self.sentence_sep_node = SentenceSepNode(seps = "。，：；？！\n ")
        self.brackets_parsor_node = BracketsParsorNode()

        async def event_emitter_lambda(_, data):
            await self.handle_event(data)

        self.event_emitter = LambdaNode(event_emitter_lambda)

        self.sentence_sep_node.connect_to(self.brackets_parsor_node)
        self.brackets_parsor_node.connect_to(self.event_emitter)

        self._curr_agent_response = ""

        # 加载command.json
        self.load_commands()

        # 注册事件处理器
        @self.on("user_input")
        async def handle_user_input(_, timestamp: str, event_data: EventData):
            """
            Handle user input event
            """
            # self.response_done = False  # 重置回复完成标志
            self.first_sentence_emitted = False
            if self.is_interaction:
                content = event_data.get("content", "")
                if not is_empty(content):
                    # 调用LLM处理用户输入
                    self.llm.append_context(content, "user")
                    await self.llm.respond_to_context()

        @self.on("start_playback")
        async def handle_start_playback(_, timestamp: str, event_data: EventData):
            """
            Handle start playback event
            """
            await self.start_playback()

        @self.on("ppt_playback_finished")
        async def handle_ppt_playback_finished(_, timestamp: str, event_data: EventData):
            """
            Handle PPT playback finished event
            """
            if not self.is_interaction:
                await self.process_next_command()

        @self.on("audio_playback_finished")
        async def handle_audio_playback_finished(_, timestamp: str, event_data: EventData):
            """
            Handle audio playback finished event
            """
            if not self.is_interaction:
                await self.process_next_command()
            else:
                await self.process_next_command_in_interaction()


        @self.on("interaction_finished")
        async def handle_interaction_finished(_, timestamp: str, event_data: EventData):
            """
            Handle interaction finished event
            """
            self.is_interaction = False
            await self.process_next_command()

    def load_commands(self):
        """
        Load commands from command.json
        """
        try:
            with open(self.command_json_path, 'r', encoding='utf-8') as f:
                self.commands = json.load(f)
            print(f"Loaded {len(self.commands)} commands from {self.command_json_path}")
        except Exception as e:
            print(f"Error loading command.json: {e}")
            self.commands = []

    async def start_playback(self):
        """
        Start playback of commands
        """
        self.is_playing = True
        if self.is_interaction:
            self.is_interaction = False

        await self.process_next_command()

    async def process_next_command(self):
        """
        Process next command in the sequence
        """
        if not self.is_playing or self.current_command_index >= len(self.commands) or self.is_interaction:
            return

        command = self.commands[self.current_command_index]
        self.current_command_index += 1

        if command["type"] == "ppt":
            await self.handle_ppt_command(command)
        elif command["type"] == "say":
            await self.handle_say_command(command)
        elif command["type"] == "interaction_start":
            await self.handle_interaction_command(command)

    async def process_next_command_in_interaction(self):
            """
            Process next command in interaction
            """
            print("DEBUG process_next_command_in_interaction")
            if self.is_interaction and self.interaction_commands:
                # 取出第一个命令并发送
                event_data = self.interaction_commands.pop(0)
                await self.emit(event_data)
                print("DEBUG audio sent:", event_data["content"])

                # 检查是否所有语音都已生成完毕
                # 条件：LLM回复已完成 且 分句节点buffer为空 且 交互命令队列为空
                # print("DEBUG 检查是否所有语音都已生成完毕")
                # print(f"LLM回复已完成: {self.response_done}")
                # print(f"分句节点buffer为空: {not self.sentence_sep_node.buffer}")
                # print(f"交互命令队列为空: {not self.interaction_commands}")
                if self.response_done and not self.sentence_sep_node.buffer and not self.interaction_commands:
                    print("!!!DEBUG response_audio_finished!!!")
                    await self.emit({"type": "response_audio_finished"})

                    self.response_done = False  # 重置回复完成标志

    async def handle_ppt_command(self, command):
        """
        Handle PPT command
        """
        page_num = command["page"]
        ppt_dir = os.path.join(os.path.dirname(self.command_json_path), "ppt")
        ppt_path = os.path.join(ppt_dir, f"{page_num}.png")

        try:
            with open(ppt_path, 'rb') as f:
                ppt_data = f.read()
            base64_ppt = base64.b64encode(ppt_data).decode("utf-8")
            await self.emit({"type": "show_ppt", "page_num": page_num, "media_data": base64_ppt, "format": "png"})
            # 清理临时变量，释放内存
            ppt_data = None
            base64_ppt = None
        except Exception as e:
            print(f"Error loading PPT: {e}")
            # 发送错误信息给前端
            await self.emit({"type": "error", "message": f"Failed to load PPT page {page_num}"})
            # 继续处理下一个命令
            await self.process_next_command()

    async def handle_say_command(self, command):
        """
        Handle say command
        """
        text = command["text"]
        audio_path = os.path.join(os.path.dirname(self.command_json_path), command["audio"])

        try:
            # 加载音频文件
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
            base64_audio = base64.b64encode(audio_data).decode("utf-8")
            
            # 构建事件数据
            event_data = {
                "type": "say_aloud",
                "content": text,
                "media_data": base64_audio,
                "format": "wav",
                "is_last": True,
                "seq": self.current_command_index - 1
            }
            
            # 添加时间戳信息（如果存在）
            if "timestamps" in command:
                event_data["timestamps"] = command["timestamps"]
            
            # 发送事件
            await self.emit(event_data)
            
            # 清理临时变量，释放内存
            audio_data = None
            base64_audio = None
        except Exception as e:
            print(f"Error loading audio: {e}")
            # 发送错误信息给前端
            await self.emit({"type": "error", "message": f"Failed to load audio {command['audio']}"})
            # 继续处理下一个命令
            await self.process_next_command()

    async def handle_interaction_command(self, command):
        """
        Handle interaction command
        """
        self.is_interaction = True
        self.interaction_commands = []
        self.interaction_duration = command["duration"]
        self.interaction_prompt = command["prompt"]
        self.first_sentence_emitted = False
        self.response_done = False  # 重置回复完成标志

        # 发送互动开始信号
        await self.emit({"type": "interaction_start", "duration": self.interaction_duration, "prompt": self.interaction_prompt})

        # 初始化LLM上下文
        self.llm_api_config.system_prompt = self.interaction_prompt
        self.llm = create_bot(**self.llm_api_config)
        # self.llm.messages = []
        # # 添加系统提示
        # self.llm.append_context(self.interaction_prompt, "system")

        @self.llm.on("start_of_response")
        async def handle_start_of_response(data):
            await self.emit({"type": "start_of_response"})

        @self.llm.on("message_delta")
        async def handle_message_delta(data):
            content_chunk = data["content"]
            
            # 2. 然后处理文本和TTS合成 - 低优先级，可延迟
            await self.sentence_sep_node.handle(content_chunk)
        
        @self.llm.on("done")
        async def handle_done(data):
            print("DEBUG: LLM response done!!!")
            self.response_done = True
            self.llm.messages.append({"role": "assistant", "content": data["content"]})
            await self.sentence_sep_node.handle(" ")
            await self.emit({"type": "end_of_response", "response": data["content"]})
            # 标记LLM回复完成
            
            # 检查AI回复中是否包含PPT翻页指令
            # response_content = data["content"]
            # import re
            
            # # 匹配多种格式：
            # # 1. [PPT_2] (来自PPT的格式)
            # # 2. [PDF_2] (来自PDF的格式)
            # # 3. [翻页:1] 或 [翻页: 1] (旧格式)
            # pattern = r'\[(?:PPT_([0-9]+)|PDF_([0-9]+)|翻页:?\s*([0-9]+))\]'
            # match = re.search(pattern, response_content)
            
            # if match:
            #     # 获取匹配到的页码（从三个捕获组中取非None的那个）
            #     page_num = int(match.group(1) if match.group(1) else (match.group(2) if match.group(2) else match.group(3)))
            #     await self.emit({"type": "flip_ppt_page", "page_num": page_num})

    async def handle_event(self, data: dict):
        """
        Handle event
        """
        data_type = data.get("type", "")
        content = data.get("content", "")

        await asyncio.sleep(0) # check point (to check if the conversation is interrupted)

        if data_type == "text":
            self._curr_agent_response += content

            # TTS合成 - 同步处理以确保字幕显示正确
            try:
                if self.tts_stream:
                    first_pack = True
                    async for media_data in self.tts.synthesize_stream(content):
                        if self.tts.format == "pcm":
                            media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                        base64_data = base64.b64encode(media_data).decode("utf-8")

                        if first_pack:
                            first_pack = False
                            display_text = content
                        else:
                            display_text = ""

                        # 构建事件数据
                        event_data = {"type": "say_aloud", "content": display_text, "media_data": base64_data, "format": "wav", "is_last": True, "seq": 0}
                        
                        # 检查是否在交互期间
                        if self.is_interaction:
                            # 首句直接发送
                            if not self.first_sentence_emitted:
                                await self.emit(event_data)
                                self.first_sentence_emitted = True
                            else:
                                # 后续句子存储到 interaction_commands
                                self.interaction_commands.append(event_data)
                        else:
                            # 非交互期间直接发送
                            await self.emit(event_data)
                else:
                    media_data = await self.tts.synthesize(content)
                    if self.tts.format == "pcm":
                        media_data = pcm2wav(media_data, sample_rate=self.tts.sample_rate, channels=self.tts.channels, bits_per_sample=self.tts.bits_per_sample)
                    base64_data = base64.b64encode(media_data).decode("utf-8")
                    # 构建事件数据
                    event_data = {"type": "say_aloud", "content": content, "media_data": base64_data, "format": "wav", "is_last": True, "seq": 0}
                    
                    # 检查是否在交互期间
                    if self.is_interaction:
                        # 首句直接发送
                        if not self.first_sentence_emitted:
                            await self.emit(event_data)
                            self.first_sentence_emitted = True
                        else:
                            # 后续句子存储到 interaction_commands
                            self.interaction_commands.append(event_data)
                    else:
                        # 非交互期间直接发送
                        await self.emit(event_data)
            except Exception as e:
                print(f"TTS合成出错: {e}")
                raise e

        elif data_type == "tag":
            self._curr_agent_response += f"[{content}]"
            await self.emit({"type": "bracket_tag", "content": content})