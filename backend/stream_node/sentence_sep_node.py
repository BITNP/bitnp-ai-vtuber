"""
Sentence separator node
"""
import re
from .absctract_stream_node import StreamNode

class SentenceSepNode(StreamNode):
    def __init__(self, seps: str = ',.:;? ，。：；？'):
        super().__init__()
        self.seps = seps
        self.buffer = ""

    async def process(self, data: str):
        self.buffer += data
        # 使用正则表达式按照多个分隔符中的任意一个来分割
        sentences = re.split(f'[{re.escape(self.seps)}]', self.buffer)
        self.buffer = sentences[-1]
        return sentences[:-1]
