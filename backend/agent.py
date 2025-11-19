import asyncio
import json
import time
import websockets

uri = "ws://0.0.0.0:8000/ws/agent/test_agent"

async def main():
    message = {"type": "event", "data": {"event_type": "SayAloud", "text": "你好"}}
    try:
        async with websockets.connect(uri) as websocket:
            while True:
                await websocket.send(json.dumps(message))
                await asyncio.sleep(1)
    except Exception as e:
        print("WebSocket 连接异常:", e)

if __name__ == "__main__":
    asyncio.run(main())
