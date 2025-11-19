"""
Accumulative list node
"""
from typing import Any
from .absctract_stream_node import StreamNode

class AccumulativeListNode(StreamNode):
    def __init__(self):
        super().__init__()
        self.buffer = []

    async def process(self, data: Any):
        # if type(data) != list:
        #     raise TypeError(f"AccumulativeListNode expects a list, but got {type(data)}")
        self.buffer.append(data)
        return None