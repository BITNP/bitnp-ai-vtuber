# -*- coding: utf-8 -*-
"""
弹幕监听服务
- 持续监听B站直播间弹幕
- 内存存储弹幕历史
- 提供HTTP API供前端查询
"""
import asyncio
import http.cookies
import argparse
import logging
from typing import List, Optional
from datetime import datetime, timezone

import aiohttp
import uvicorn
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

import blivedm
import blivedm.models.web as web_models

# 配置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('danmaku_server.log')
    ]
)
logger = logging.getLogger(__name__)

# 弹幕存储 - 内存中的列表
danmaku_history: List[dict] = []

# 配置
app = FastAPI(title="Danmaku Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 弹幕处理器
class DanmakuHandler(blivedm.BaseHandler):
    def _on_danmaku(self, client: blivedm.BLiveClient, message: web_models.DanmakuMessage):
        """收到弹幕时的处理"""
        try:
            danmaku_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "room_id": client.room_id,
                "uname": message.uname,
                "uid": message.uid,
                "msg": message.msg,
                "is_admin": bool(message.admin),
                "is_vip": bool(message.vip),
                "is_svip": bool(message.svip)
            }
            danmaku_history.append(danmaku_data)
            logger.info(f'[{client.room_id}] {message.uname}：{message.msg}')
        except Exception as e:
            logger.error(f'处理弹幕失败: {e}')

    def _on_gift(self, client: blivedm.BLiveClient, message: web_models.GiftMessage):
        """收到礼物时的处理"""
        try:
            gift_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "room_id": client.room_id,
                "uname": message.uname,
                "gift_name": message.gift_name,
                "num": message.num,
                "coin_type": message.coin_type,
                "total_coin": message.total_coin,
                "type": "gift"
            }
            danmaku_history.append(gift_data)
            logger.info(f'[{client.room_id}] {message.uname} 赠送{message.gift_name}x{message.num}')
        except Exception as e:
            logger.error(f'处理礼物失败: {e}')

    def _on_super_chat(self, client: blivedm.BLiveClient, message: web_models.SuperChatMessage):
        """收到醒目留言时的处理"""
        try:
            sc_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "room_id": client.room_id,
                "uname": message.uname,
                "message": message.message,
                "price": message.price,
                "type": "super_chat"
            }
            danmaku_history.append(sc_data)
            logger.info(f'[{client.room_id}] 醒目留言 ¥{message.price} {message.uname}：{message.message}')
        except Exception as e:
            logger.error(f'处理醒目留言失败: {e}')

    def _on_unknown_command(self, client: blivedm.BLiveClient, command: dict):
        """处理未知命令（如 ONLINE_RANK_V3 等）"""
        cmd = command.get('cmd', 'UNKNOWN')
        logger.debug(f'收到未知命令: {cmd}')
        # 不做任何处理，只是记录日志，避免影响其他消息处理


# HTTP接口
@app.get("/danmaku")
async def get_danmaku(
    since: Optional[str] = Query(None, description="获取此时间戳之后的弹幕，格式为ISO 8601"),
    room_id: Optional[int] = Query(None, description="按直播间ID过滤")
):
    """
    获取弹幕列表
    - since: 可选，获取指定时间之后的弹幕
    - room_id: 可选，按直播间ID过滤
    """
    result = danmaku_history
    
    if since:
        result = [d for d in result if d["timestamp"] > since]
    
    if room_id:
        result = [d for d in result if d.get("room_id") == room_id]
    
    return {"count": len(result), "data": result}


@app.get("/danmaku/count")
async def get_danmaku_count():
    """获取弹幕总数"""
    return {"total_count": len(danmaku_history)}


@app.delete("/danmaku")
async def clear_danmaku():
    """清空弹幕历史"""
    danmaku_history.clear()
    return {"message": "清空成功"}


async def run_danmaku_client(room_ids: List[int], sessdata: str = ""):
    """运行弹幕监听客户端"""
    cookies = http.cookies.SimpleCookie()
    if sessdata:
        cookies['SESSDATA'] = sessdata
        cookies['SESSDATA']['domain'] = 'bilibili.com'
    
    session = aiohttp.ClientSession()
    if sessdata:
        session.cookie_jar.update_cookies(cookies)
    
    clients = []
    handler = DanmakuHandler()
    
    for room_id in room_ids:
        client = blivedm.BLiveClient(room_id, session=session)
        client.set_handler(handler)
        client.start()
        clients.append(client)
        logger.info(f"开始监听直播间: {room_id}")
    
    try:
        await asyncio.gather(*(client.join() for client in clients))
    finally:
        await asyncio.gather(*(client.stop_and_close() for client in clients))
        await session.close()


async def main():
    parser = argparse.ArgumentParser(description="弹幕监听服务")
    parser.add_argument("--room-ids", type=str, required=True, help="直播间ID列表，用逗号分隔")
    parser.add_argument("--port", type=int, default=8001, help="HTTP服务端口，默认8001")
    parser.add_argument("--sessdata", type=str, default="", help="B站SESSDATA cookie，可选")
    args = parser.parse_args()
    
    room_ids = [int(r.strip()) for r in args.room_ids.split(",")]
    
    # 同时运行弹幕监听和HTTP服务
    tasks = [
        run_danmaku_client(room_ids, args.sessdata),
        asyncio.create_task(run_http_server(args.port))
    ]
    
    await asyncio.gather(*tasks)


async def run_http_server(port: int):
    """运行HTTP服务器"""
    config = uvicorn.Config(app, host="0.0.0.0", port=port)
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == '__main__':
    asyncio.run(main())