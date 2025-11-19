"""
AI VTuber Agent (behavior controller)
"""

from ..llm_api import create_bot
from typing import Literal, Union, Callable

import asyncio
import json
import websockets

BotConfig = dict[Union[Literal["api_name"], str], str]
TimeStampISO = str
EventData = dict

class Agent:
    def __init__(self, server_url: str, agent_name: str, llm_api_config: BotConfig = None):

        if not (server_url.startswith("ws://") or server_url.startswith("wss://")):
            if server_url.startswith("https://"):
                server_url = server_url.replace("https://", "wss://", 1)
            elif server_url.startswith("http://"):
                server_url = server_url.replace("http://", "ws://", 1)
            else:
                server_url = "ws://" + server_url
        
        server_url = server_url.rstrip('/')

        self.server_url = server_url
        self.agent_name = agent_name
        self.llm = create_bot(**llm_api_config) if llm_api_config else None

        self._event_handlers: dict[str, list[Callable[['Agent', TimeStampISO, EventData], None]]] = {}
        self.ws = None
    
    def on(self, event_type: str):
        """
        Register a handler function for a specific event type.
        Or register a loop function that will be called every time the agent receives a message. (when event_type is "loop")
        
        Args:
            event_type (str): The type of event to handle.
        
        Reserved event types:
            "loop": The function will be called every 0.1 seconds.

        Usage:
            ```
            @agent.on("loop")
            async def loop_func(self, timestamp: str, event_data: EventData):
                ...
            
            @agent.on("user_input")
            async def handle_user_input(self, timestamp: str, event_data: EventData):
                ...
            ```
        """
        def decorator(func: Callable['Agent', TimeStampISO, EventData]):
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(func)
            return func
        return decorator
    
    async def emit(self, event_data: dict):
        """
        Emit an event to the server.
        
        Args:
            event_data (dict): The event data to emit.
        """
        if self.ws:
            await self.ws.send(json.dumps({"type": "event", "data": event_data}))

    async def run(self):
        """
        Agent main loop
        """
        uri = f"{self.server_url}/ws/agent/{self.agent_name}"

        async with websockets.connect(uri) as ws:
            self.ws = ws
            while True:
                try:
                    # loop functions
                    if "loop" in self._event_handlers:
                        for handler in self._event_handlers["loop"]:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(self, "", {})
                            else:
                                handler(self, "", {})
                    message = await asyncio.wait_for(ws.recv(), timeout=0.1)  # 0.1 秒超时
                    try:
                        message = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    if type(message) is not dict:
                        continue

                    time_iso: str = message.get("time", "")
                    event_data: dict = message.get("data", {})
                    event_type: str = event_data.get("type", "")

                    # event handlers
                    if event_type != "loop" and event_type in self._event_handlers:
                        for handler in self._event_handlers[event_type]:
                            if asyncio.iscoroutinefunction(handler):
                                await handler(self, time_iso, event_data)
                            else:
                                handler(self, time_iso, event_data)
                    
                    # 例如：await self.handle_event(message)
                except websockets.ConnectionClosed:
                    # 连接断开，退出循环
                    break
