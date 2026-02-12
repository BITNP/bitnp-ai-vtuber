"""
Sentence separator node
"""
import re
from .absctract_stream_node import StreamNode

class SentenceSepNode(StreamNode):
    def __init__(self, seps: str = ',.:;?!，。：；？！\n', keep_seps: bool = True):
        super().__init__()
        self.seps = seps
        self.keep_seps = keep_seps
        self.buffer = ""

    def reset(self):
        self.buffer = ""

    async def process(self, data: str):
        self.buffer += data
        # 使用正则表达式按照多个分隔符中的任意一个来分割
        split = re.split(f'[{re.escape(self.seps)}]', self.buffer)

        if self.keep_seps:
            seps = re.findall(f'[{re.escape(self.seps)}]', self.buffer)
            sentences = [sentence + sep for sentence, sep in zip(split[:-1], seps)]
        else:
            sentences = split[:-1]

        self.buffer = split[-1]
        return sentences

    async def flush(self):
        if not self.buffer:
            return
        remaining = self.buffer
        self.buffer = ""
        if self.next_nodes:
            for next_node in self.next_nodes:
                await next_node.handle(remaining)
