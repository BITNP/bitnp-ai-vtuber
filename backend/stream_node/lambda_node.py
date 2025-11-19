"""
Lambda node
"""
from typing import Callable, Any
from .absctract_stream_node import StreamNode

import asyncio

class LambdaNode(StreamNode):
    def __init__(self, func: Callable[['StreamNode', Any], Any]):
        super().__init__()
        self.func = func

    async def process(self, data):
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(self, data)
        else:
            return self.func(self, data)