"""
聊天服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from database.models import ChatMessage, MessageType, Friendship, FriendshipStatus
from typing import List, Dict, Optional
from datetime import datetime


class ChatService:
    """聊天服务"""
    
    @staticmethod
    def check_friendship(db: Session, user_id: int, friend_id: int) -> bool:
        """
        检查是否为好友关系
        :param db: 数据库会话
        :param user_id: 用户ID
        :param friend_id: 好友ID
        :return: 是否为好友
        """
        friendship = db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
            ),
            Friendship.status == FriendshipStatus.accepted
        ).first()
        
        return friendship is not None
    
    @staticmethod
    def send_message(
        db: Session,
        from_user_id: int,
        to_user_id: int,
        content: str,
        message_type: str = "text"
    ) -> Dict:
        """
        发送消息
        :param db: 数据库会话
        :param from_user_id: 发送者ID
        :param to_user_id: 接收者ID
        :param content: 消息内容
        :param message_type: 消息类型
        :return: 消息信息
        """
        # 检查是否为好友
        if not ChatService.check_friendship(db, from_user_id, to_user_id):
            return {"success": False, "message": "只能给好友发送消息"}
        
        # 创建消息
        message = ChatMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            content=content,
            message_type=MessageType[message_type]
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        
        return {
            "success": True,
            "message_id": message.id,
            "from_user_id": message.from_user_id,
            "to_user_id": message.to_user_id,
            "content": message.content,
            "message_type": message.message_type.value,
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat()
        }
    
    @staticmethod
    def get_chat_history(
        db: Session,
        user_id: int,
        friend_id: int,
        limit: int = 50,
        before_message_id: Optional[int] = None
    ) -> List[Dict]:
        """
        获取聊天历史
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 好友ID
        :param limit: 返回数量
        :param before_message_id: 在此消息之前的消息（用于分页）
        :return: 消息列表
        """
        # 构建查询
        query = db.query(ChatMessage).filter(
            or_(
                and_(ChatMessage.from_user_id == user_id, ChatMessage.to_user_id == friend_id),
                and_(ChatMessage.from_user_id == friend_id, ChatMessage.to_user_id == user_id)
            )
        )
        
        # 分页
        if before_message_id:
            query = query.filter(ChatMessage.id < before_message_id)
        
        # 按时间倒序，取最新的N条
        messages = query.order_by(desc(ChatMessage.created_at)).limit(limit).all()
        
        # 转换为正序（旧消息在前）
        messages.reverse()
        
        result = []
        for msg in messages:
            result.append({
                "message_id": msg.id,
                "from_user_id": msg.from_user_id,
                "to_user_id": msg.to_user_id,
                "content": msg.content,
                "message_type": msg.message_type.value,
                "is_read": msg.is_read,
                "read_at": msg.read_at.isoformat() if msg.read_at else None,
                "created_at": msg.created_at.isoformat()
            })
        
        return result
    
    @staticmethod
    def mark_as_read(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        标记消息为已读
        :param db: 数据库会话
        :param user_id: 当前用户ID（接收者）
        :param friend_id: 好友ID（发送者）
        :return: 结果
        """
        # 查找所有未读消息
        messages = db.query(ChatMessage).filter(
            ChatMessage.from_user_id == friend_id,
            ChatMessage.to_user_id == user_id,
            ChatMessage.is_read == 0
        ).all()
        
        # 标记为已读
        count = 0
        now = datetime.now()
        for msg in messages:
            msg.is_read = 1
            msg.read_at = now
            count += 1
        
        db.commit()
        
        return {"success": True, "count": count}
    
    @staticmethod
    def get_unread_count(db: Session, user_id: int, friend_id: Optional[int] = None) -> int:
        """
        获取未读消息数
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 好友ID（可选，不传则返回总未读数）
        :return: 未读消息数
        """
        query = db.query(ChatMessage).filter(
            ChatMessage.to_user_id == user_id,
            ChatMessage.is_read == 0
        )
        
        if friend_id:
            query = query.filter(ChatMessage.from_user_id == friend_id)
        
        return query.count()
    
    @staticmethod
    def get_conversation_list(db: Session, user_id: int) -> List[Dict]:
        """
        获取会话列表（最近联系人）
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 会话列表
        """
        from sqlalchemy import func
        from database.models import User
        
        # 子查询：获取每个会话的最新消息
        subquery = db.query(
            func.greatest(ChatMessage.from_user_id, ChatMessage.to_user_id).label('user1'),
            func.least(ChatMessage.from_user_id, ChatMessage.to_user_id).label('user2'),
            func.max(ChatMessage.id).label('last_message_id')
        ).filter(
            or_(
                ChatMessage.from_user_id == user_id,
                ChatMessage.to_user_id == user_id
            )
        ).group_by('user1', 'user2').subquery()
        
        # 获取最新消息详情
        messages = db.query(ChatMessage).join(
            subquery,
            ChatMessage.id == subquery.c.last_message_id
        ).order_by(desc(ChatMessage.created_at)).all()
        
        result = []
        for msg in messages:
            # 确定对方ID
            friend_id = msg.to_user_id if msg.from_user_id == user_id else msg.from_user_id
            
            # 获取对方信息
            friend = db.query(User).filter(User.id == friend_id).first()
            if not friend:
                continue
            
            # 获取未读数
            unread_count = ChatService.get_unread_count(db, user_id, friend_id)
            
            result.append({
                "friend_id": friend.id,
                "friend_name": friend.username,
                "friend_student_id": friend.student_id,
                "last_message": msg.content,
                "last_message_type": msg.message_type.value,
                "last_message_time": msg.created_at.isoformat(),
                "unread_count": unread_count,
                "is_from_me": msg.from_user_id == user_id
            })
        
        return result
