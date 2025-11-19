"""
Lambda node
"""
from typing import Callable, Any
from .absctract_stream_node import StreamNode
class LambdaNode(StreamNode):
    def __init__(self, func: Callable[['StreamNode', Any], Any]):
        super().__init__()
        self.func = func

    async def process(self, data):
        return self.func(self, data)