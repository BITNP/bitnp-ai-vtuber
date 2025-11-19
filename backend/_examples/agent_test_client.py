import asyncio
import websockets
import json

async def send_message():
    uri = "ws://localhost:8000/ws/frontend/shumeiniang"
    # 定义要发送的特定信息
    message = {
        "type": "event",
        "data": {
            "type": "user_input",
            "content": "你好，你是谁？"
        }
    }
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(message))
            print("已发送消息:", message)
            # 可选：等待服务器响应
            response = await websocket.recv()
            print("收到服务器响应:", response)
    except Exception as e:
        print("连接失败:", e)

if __name__ == "__main__":
    asyncio.run(send_message())
