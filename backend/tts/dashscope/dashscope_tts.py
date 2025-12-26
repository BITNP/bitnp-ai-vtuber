import os
import requests
import base64
import pathlib
import threading
import time
import dashscope  # DashScope Python SDK 版本需要不低于1.23.9
import queue
import asyncio

from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback, AudioFormat
from ..abstract_tts import AbstractTTS
from typing import Literal, AsyncGenerator, Callable, List

PCM_Format = Literal['pcm']

URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
DEFAULT_TARGET_MODEL = "qwen3-tts-vc-realtime-2025-11-27"

class DashscopeTTS(AbstractTTS):
    """
    Dashscope TTS
    """

    def __init__(self, api_key: str, voice: str, model: str = DEFAULT_TARGET_MODEL):
        super().__init__(format='pcm', sample_rate=24000, channels=1, bits_per_sample=16)
        
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.audio_queue = queue.Queue()
        self.complete_event = threading.Event()
        self.error_event = threading.Event()
        self.error_message = None
        self._callback = None
        self._qwen_tts_realtime = None
        
    class AsyncCallback(QwenTtsRealtimeCallback):
        def __init__(self, audio_queue: queue.Queue, complete_event: threading.Event, 
                    error_event: threading.Event, error_message: List):
            self.audio_queue = audio_queue
            self.complete_event = complete_event
            self.error_event = error_event
            self.error_message = error_message
            
        def on_open(self) -> None:
            print('[TTS] 连接已建立')
            
        def on_close(self, close_status_code, close_msg) -> None:
            print(f'[TTS] 连接关闭 code={close_status_code}, msg={close_msg}')
            if close_status_code != 1000:  # 非正常关闭
                self.error_message.append(f"连接关闭: code={close_status_code}, msg={close_msg}")
                self.error_event.set()
            self.complete_event.set()
            
        def on_event(self, response: dict) -> None:
            try:
                event_type = response.get('type', '')
                if event_type == 'session.created':
                    print(f'[TTS] 会话开始: {response["session"]["id"]}')
                elif event_type == 'response.audio.delta':
                    audio_data = base64.b64decode(response['delta'])
                    self.audio_queue.put(audio_data)
                elif event_type == 'response.done':
                    print(f'[TTS] 响应完成')
                elif event_type == 'session.finished':
                    print('[TTS] 会话结束')
                    self.complete_event.set()
            except Exception as e:
                print(f'[Error] 处理回调事件异常: {e}')
                self.error_message.append(str(e))
                self.error_event.set()
                self.complete_event.set()
    
    async def synthesize_stream(self, text: str, chunk_delay: float = 0.1) -> AsyncGenerator[bytes, None]:
        """
        生成语音数据的异步生成器
        
        Args:
            text: 要合成的文本
            chunk_delay: 发送文本块之间的延迟（秒）
            
        Yields:
            bytes: PCM音频数据块
        """
        # 初始化dashscope
        dashscope.api_key = self.api_key
        
        # 清空状态
        self.audio_queue = queue.Queue()
        self.complete_event = threading.Event()
        self.error_event = threading.Event()
        self.error_message = []
        
        # 创建回调
        self._callback = self.AsyncCallback(
            self.audio_queue, 
            self.complete_event, 
            self.error_event, 
            self.error_message
        )
        
        # 创建TTS实时实例
        self._qwen_tts_realtime = QwenTtsRealtime(
            model=self.model,
            callback=self._callback,
            url=URL
        )
        
        # 连接并设置参数
        self._qwen_tts_realtime.connect()
        self._qwen_tts_realtime.update_session(
            voice=self.voice,
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode='server_commit'
        )
        
        # 启动后台线程发送文本
        def send_texts():
            try:
                print(f'[发送文本]: {text}')
                self._qwen_tts_realtime.append_text(text)
                time.sleep(chunk_delay)
                self._qwen_tts_realtime.finish()
            except Exception as e:
                print(f'[Error] 发送文本异常: {e}')
                self.error_message.append(str(e))
                self.error_event.set()
                self.complete_event.set()
        
        send_thread = threading.Thread(target=send_texts, daemon=True)
        send_thread.start()
        
        # 异步生成音频数据
        try:
            while not self.complete_event.is_set():
                try:
                    # 非阻塞获取音频数据
                    audio_data = self.audio_queue.get(timeout=0.1)
                    yield audio_data
                except queue.Empty:
                    # 检查是否出错
                    if self.error_event.is_set():
                        raise Exception(f"TTS合成出错: {self.error_message}")
                    # 继续等待
                    await asyncio.sleep(0.01)
                except Exception as e:
                    print(f'[Error] 获取音频数据异常: {e}')
                    break
            
            # 处理队列中剩余的数据
            while not self.audio_queue.empty():
                try:
                    audio_data = self.audio_queue.get_nowait()
                    yield audio_data
                except queue.Empty:
                    break
            
        finally:
            # 清理资源
            if self._qwen_tts_realtime:
                self._qwen_tts_realtime.close()
            
    async def synthesize(self, text: str, chunk_delay: float = 0.1) -> bytes:
        """
        生成完整的音频数据
        
        Args:
            text: 要合成的文本
            chunk_delay: 发送文本块之间的延迟（秒）
            
        Returns:
            bytes: 完整的PCM音频数据
        """
        audio_chunks = []
        async for chunk in self.synthesize_stream(text, chunk_delay):
            audio_chunks.append(chunk)
        return b''.join(audio_chunks)

