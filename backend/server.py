"""
A server for communication between frontend and agents (or between agents)

提供以下接口：
    - /ws/agent: 智能体连接此端口
    - /ws/frontend: 前端连接此端口
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

import json
import uvicorn
import logging
import uuid
import argparse

# 配置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('vtuber_server.log') # record log to file
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="BITNP AI VTuber Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该指定具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 连接管理器 - 智能体和前端分别使用
class ConnectionManager:
    def __init__(self, name: str = "default"):
        # 存储活跃连接：client_id -> WebSocket
        self.active_connections: dict[str, WebSocket] = {}
        # 存储用户信息：client_id -> user_info
        self.users: dict[str, dict] = {}
        self.name = name
    
    def log(self, message: str):
        """记录日志"""
        logger.info(f"[{self.name} manager] {message}")

    async def connect(self, websocket: WebSocket, user_data: dict):
        """接受WebSocket连接并存储用户信息"""
        await websocket.accept()
        
        # 生成唯一客户端ID
        client_id = str(uuid.uuid4())
        
        # 存储连接和用户信息
        self.active_connections[client_id] = websocket
        self.users[client_id] = {
            "client_id": client_id,
            "agent_name": user_data.get("agent_name", ""),
            "join_time": datetime.now().isoformat(),
            **user_data  # 包含其他用户数据
        }
        
        self.log(f"Connected! agent_name: {user_data.get('agent_name')}, client_id: {client_id}")
        
        # 发送连接成功消息
        welcome_msg = {
            "type": "system",
            "message": "successfully connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_personal_message(json.dumps(welcome_msg), client_id)
        return client_id

    async def disconnect(self, client_id: str):
        """处理连接断开"""
        if client_id in self.active_connections:
            # 移除连接
            del self.active_connections[client_id]
            del self.users[client_id]

    async def send_personal_message(self, message: str, client_id: str):
        """向特定客户端发送消息"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(message)
            except Exception as e:
                logging.info(f"发送消息到客户端 {client_id} 失败: {e}")
                await self.disconnect(client_id)

    async def broadcast(self, message: str, exclude_client_id: str = None):
        """广播消息给所有客户端"""
        disconnected_clients = []
        
        for client_id, connection in self.active_connections.items():
            if client_id != exclude_client_id:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logging.info(f"广播消息到客户端 {client_id} 失败: {e}")
                    disconnected_clients.append(client_id)
        
        # 清理断开连接的客户端
        for client_id in disconnected_clients:
            await self.disconnect(client_id)
    
    def get_client_ids_by_agent_name(self, agent_name: str) -> list[str]:
        """根据智能体名称获取所有连接的客户端ID"""
        return [
            client_id for client_id, user_info in self.users.items()
            if user_info.get("agent_name") == agent_name
        ]

    def get_online_users(self):
        """获取在线用户列表"""
        return [
            {
                "agent_name": user_info.get("agent_name", ""),
                "client_id": user_info.get("client_id", ""),
                "join_time": user_info.get("join_time", "")
            }
            for user_info in self.users.values()
        ]

# 创建连接管理器实例
agent_manager = ConnectionManager('agent')
frontend_manager = ConnectionManager('frontend')

# 存储已连接的智能体
connected_agents: set[str] = set()

async def handle_agent_message(client_id: str, message_data: dict) -> dict | None:
    """处理智能体发送的消息"""
    # logging.info(f"智能体 {client_id} 发送消息: {message_data}") # DEBUG

    message_type = message_data.get("type", "")

    if message_type == "":
        return {"type": "error", "message": "empty message type"}

    elif message_type == "disconnect":
        await agent_manager.disconnect(client_id)
        return None

    elif message_type == "event":
        # 向前端发送事件
        event_data = message_data.get("data", "")
        agent_name = agent_manager.users.get(client_id, {}).get("agent_name", "")
        for client_id in frontend_manager.get_client_ids_by_agent_name(agent_name):
            await frontend_manager.send_personal_message(json.dumps({"time": datetime.now().isoformat(), "data": event_data}), client_id)
        return {"type": "success", "message": "event sent"}

async def handle_frontend_message(client_id: str, message_data: dict) -> dict | None:
    """处理前端发送的消息"""
    # logging.info(f"前端 {client_id} 发送消息: {message_data}") # DEBUG

    message_type = message_data.get("type", "")

    if message_type == "":
        return {"type": "error", "message": "empty message type"}
    
    elif message_type == "disconnect":
        await frontend_manager.disconnect(client_id)
        return None

    elif message_type == "is_agent_online":
        # 查询agent是否在线
        agent_name = frontend_manager.users.get(client_id, {}).get("agent_name", "")
        if agent_name in connected_agents:
            return {"type": "success", "message": True}
        else:
            return {"type": "success", "message": False}

    elif message_type == "event":
        # 向智能体发送事件
        event_data = message_data.get("data", {})
        agent_name = frontend_manager.users.get(client_id, {}).get("agent_name", "")
        for client_id in agent_manager.get_client_ids_by_agent_name(agent_name):
            # logging.info(f"向智能体 {agent_name} 发送事件: {event_data}") # DEBUG
            await agent_manager.send_personal_message(json.dumps({"time": datetime.now().isoformat(), "data": event_data}), client_id)
        return {"type": "success", "message": "event sent"}

# 智能体 WebSocket 端点
@app.websocket("/ws/agent/{agent_name}")
async def ws_agent(websocket: WebSocket, agent_name: str):
    """智能体 WebSocket 端点"""

    if agent_name in connected_agents:
        logging.error(f"Agent {agent_name} is already connected, but trying to connect again")
        await websocket.close(code=4001, reason="Agent name already connected")
        return
    
    connected_agents.add(agent_name)

    user_data = {
        "agent_name": agent_name,
        "connect_time": datetime.now().isoformat()
    }
    
    client_id = await agent_manager.connect(websocket, user_data)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # 处理不同类型的消息
            res = await handle_agent_message(client_id, message_data)
            if res:
                await agent_manager.send_personal_message(json.dumps(res), client_id)
            
    except WebSocketDisconnect:
        connected_agents.remove(agent_name)
        await agent_manager.disconnect(client_id)
    except Exception as e:
        logging.error(f"WebSocket error encountered: {e}")
        connected_agents.remove(agent_name)
        await agent_manager.disconnect(client_id)

# 前端 WebSocket 端点
@app.websocket("/ws/frontend/{agent_name}")
async def ws_frontend(websocket: WebSocket, agent_name: str):
    """前端 WebSocket 端点"""
    # 准备用户数据
    user_data = {
        "agent_name": agent_name,
        "connect_time": datetime.now().isoformat()
    }
    
    client_id = await frontend_manager.connect(websocket, user_data)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # 处理不同类型的消息
            res = await handle_frontend_message(client_id, message_data)
            if res:
                await frontend_manager.send_personal_message(json.dumps(res), client_id)
            
    except WebSocketDisconnect:
        await frontend_manager.disconnect(client_id)
    except Exception as e:
        logging.error(f"WebSocket error encountered: {e}")
        await frontend_manager.disconnect(client_id)

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="BITNP AI VTuber backend")
    parser.add_argument("--port", type=int, default=8000, help="server port, defaults to 8000")
    args = parser.parse_args()

    port = args.port

    uvicorn.run(app, host="0.0.0.0", port=port)
