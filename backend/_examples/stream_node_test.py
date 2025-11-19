import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from stream_node import *

sep = SentenceSepNode(seps=",.:;? ，。：；？")
acc = AccumulativeListNode()
brackets_parsor = BracketsParsorNode()
printer = LambdaNode(lambda self, x: print(x))

sep.connect_to(brackets_parsor)
brackets_parsor.connect_to(acc)
brackets_parsor.connect_to(printer)

async def test_sentence_sep_node():
    await sep.handle('你好，我是树莓娘[点头]你好,woshi')
    await sep.handle('树莓娘[wink]？？？我是谁呀')
    await sep.handle('我是树莓[摇头]娘')
    await sep.handle(' ')
    # print(acc.buffer)

asyncio.run(test_sentence_sep_node())