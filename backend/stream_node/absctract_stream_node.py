"""
Abstract stream node
"""
from abc import ABC, abstractmethod

class StreamNode(ABC):
    def __init__(self):
        self.next_nodes: list['StreamNode'] = []
        self.extract: bool = True

    @abstractmethod
    async def process(self, data):
        pass

    async def handle(self, data):
        if self.extract and type(data) is list:
            for d in data:
                await self.handle(d)
        else:
            result = await self.process(data)
            if self.next_nodes:
                for next_node in self.next_nodes:
                    await next_node.handle(result)

    def connect_to(self, next_node: 'StreamNode'):
        self.next_nodes.append(next_node)
