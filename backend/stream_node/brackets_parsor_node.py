"""
Brackets parsor node
"""

import re
from .absctract_stream_node import StreamNode

class BracketsParsorNode(StreamNode):
    def __init__(self):
        super().__init__()
    
    async def process(self, data: str):
        split = re.split(r'\[.*?\]', data)
        tags = re.findall(r'\[(.*?)\]', data)

        # NOTE: len(tags) == len(split) - 1

        results = []

        for i in range(len(split)):

            if split[i] != "":
                results.append({"type": "text", "content": split[i]})

            if i < len(tags):
                results.append({"type": "tag", "content": tags[i]})
        
        return results