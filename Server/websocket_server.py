"""
WebSocket即时通讯服务器
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set
import json
import asyncio
from utils.redis_client import redis_client
from database.db import get_default_db
from services.chat_service import ChatService


class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 存储活跃连接：{user_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        # 存储用户的所有连接（支持多设备）：{user_id: Set[websocket]}
        self.user_connections: Dict[int, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """
        建立连接
        :param websocket: WebSocket连接
        :param user_id: 用户ID
        """
        await websocket.accept()
        
        # 添加到连接池
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(websocket)
        
        # 更新在线状态（Redis）
        redis_client.hset(f"user:online:{user_id}", "is_online", "1")
        redis_client.hset(f"user:online:{user_id}", "last_seen", str(asyncio.get_event_loop().time()))
        
        print(f"User {user_id} connected. Total connections: {len(self.user_connections[user_id])}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """
        断开连接
        :param websocket: WebSocket连接
        :param user_id: 用户ID
        """
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            
            # 如果用户没有其他连接，标记为离线
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                redis_client.hset(f"user:online:{user_id}", "is_online", "0")
                redis_client.hset(f"user:online:{user_id}", "last_seen", str(asyncio.get_event_loop().time()))
        
        print(f"User {user_id} disconnected")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """
        发送消息给指定用户
        :param message: 消息内容
        :param user_id: 用户ID
        """
        if user_id in self.user_connections:
            # 发送给该用户的所有连接（多设备）
            disconnected = set()
            for websocket in self.user_connections[user_id]:
                try:
                    await websocket.send_json(message)
                except Exception as e:
                    print(f"Error sending message to user {user_id}: {e}")
                    disconnected.add(websocket)
            
            # 清理断开的连接
            for ws in disconnected:
                self.disconnect(ws, user_id)
    
    async def broadcast(self, message: dict, exclude_user: int = None):
        """
        广播消息给所有在线用户
        :param message: 消息内容
        :param exclude_user: 排除的用户ID
        """
        for user_id, connections in self.user_connections.items():
            if exclude_user and user_id == exclude_user:
                continue
            await self.send_personal_message(message, user_id)
    
    def is_online(self, user_id: int) -> bool:
        """
        检查用户是否在线
        :param user_id: 用户ID
        :return: 是否在线
        """
        return user_id in self.user_connections and len(self.user_connections[user_id]) > 0


# 全局连接管理器
manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, user_id: int):
    """
    处理WebSocket连接
    :param websocket: WebSocket连接
    :param user_id: 用户ID
    """
    await manager.connect(websocket, user_id)
    
    try:
        # 发送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "message": "WebSocket连接成功",
            "user_id": user_id
        })
        
        # 持续接收消息
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # 处理不同类型的消息
            message_type = message_data.get("type")
            
            if message_type == "chat":
                # 聊天消息
                await handle_chat_message(websocket, user_id, message_data)
            
            elif message_type == "ping":
                # 心跳检测
                await websocket.send_json({"type": "pong"})
            
            elif message_type == "typing":
                # 正在输入状态
                to_user_id = message_data.get("to_user_id")
                if to_user_id:
                    await manager.send_personal_message({
                        "type": "typing",
                        "from_user_id": user_id,
                        "is_typing": message_data.get("is_typing", True)
                    }, to_user_id)
            
            else:
                # 未知消息类型
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {message_type}"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


async def handle_chat_message(websocket: WebSocket, from_user_id: int, message_data: dict):
    """
    处理聊天消息
    :param websocket: WebSocket连接
    :param from_user_id: 发送者ID
    :param message_data: 消息数据
    """
    to_user_id = message_data.get("to_user_id")
    content = message_data.get("content")
    message_type = message_data.get("message_type", "text")
    
    if not to_user_id or not content:
        await websocket.send_json({
            "type": "error",
            "message": "消息格式错误"
        })
        return
    
    # 保存消息到数据库
    db = next(get_default_db())
    try:
        result = ChatService.send_message(
            db,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            content=content,
            message_type=message_type
        )
        
        if not result.get("success", True):
            await websocket.send_json({
                "type": "error",
                "message": result["message"]
            })
            return
        
        # 构建消息
        message = {
            "type": "message",
            "message_id": result["message_id"],
            "from_user_id": from_user_id,
            "to_user_id": to_user_id,
            "content": content,
            "message_type": message_type,
            "created_at": result["created_at"]
        }
        
        # 发送给接收者
        await manager.send_personal_message(message, to_user_id)
        
        # 发送确认给发送者
        await websocket.send_json({
            "type": "sent",
            "message_id": result["message_id"],
            "created_at": result["created_at"]
        })
    
    except Exception as e:
        print(f"Error handling chat message: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "发送消息失败"
        })
    finally:
        db.close()


def get_online_status(user_id: int) -> dict:
    """
    获取用户在线状态
    :param user_id: 用户ID
    :return: 在线状态
    """
    is_online = manager.is_online(user_id)
    
    if is_online:
        return {
            "user_id": user_id,
            "is_online": True,
            "last_seen": None
        }
    
    # 从Redis获取最后在线时间
    last_seen = redis_client.hget(f"user:online:{user_id}", "last_seen")
    
    return {
        "user_id": user_id,
        "is_online": False,
        "last_seen": last_seen
    }
