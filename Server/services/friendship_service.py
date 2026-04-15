"""
好友系统服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from database.models import Friendship, FriendshipStatus, User
from typing import List, Dict, Optional


class FriendshipService:
    """好友服务"""
    
    @staticmethod
    def search_users_by_student_id(db: Session, student_id: str, current_user_id: int) -> List[Dict]:
        """
        通过学号搜索用户
        :param db: 数据库会话
        :param student_id: 学号（支持模糊搜索）
        :param current_user_id: 当前用户ID
        :return: 用户列表
        """
        users = db.query(User).filter(
            User.student_id.like(f"%{student_id}%"),
            User.id != current_user_id  # 排除自己
        ).limit(20).all()
        
        result = []
        for user in users:
            # 检查好友关系
            friendship = db.query(Friendship).filter(
                or_(
                    and_(Friendship.user_id == current_user_id, Friendship.friend_id == user.id),
                    and_(Friendship.user_id == user.id, Friendship.friend_id == current_user_id)
                )
            ).first()
            
            friendship_status = friendship.status.value if friendship else None
            
            result.append({
                "user_id": user.id,
                "username": user.username,
                "student_id": user.student_id,
                "school_id": user.school_id,
                "college_id": user.college_id,
                "major_id": user.major_id,
                "class_name": user.class_name,
                "friendship_status": friendship_status
            })
        
        return result
    
    @staticmethod
    def send_friend_request(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        发送好友请求
        :param db: 数据库会话
        :param user_id: 发起者ID
        :param friend_id: 目标用户ID
        :return: 结果
        """
        # 检查是否已存在好友关系
        existing = db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
            )
        ).first()
        
        if existing:
            if existing.status == FriendshipStatus.accepted:
                return {"success": False, "message": "已经是好友"}
            elif existing.status == FriendshipStatus.pending:
                return {"success": False, "message": "好友请求已发送，等待对方确认"}
            elif existing.status == FriendshipStatus.blocked:
                return {"success": False, "message": "无法添加该用户"}
        
        # 创建好友请求
        friendship = Friendship(
            user_id=user_id,
            friend_id=friend_id,
            status=FriendshipStatus.pending
        )
        db.add(friendship)
        db.commit()
        
        return {"success": True, "message": "好友请求已发送"}
    
    @staticmethod
    def accept_friend_request(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        接受好友请求
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 发起者ID
        :return: 结果
        """
        # 查找待确认的好友请求
        friendship = db.query(Friendship).filter(
            Friendship.user_id == friend_id,
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.pending
        ).first()
        
        if not friendship:
            return {"success": False, "message": "好友请求不存在"}
        
        # 更新状态
        friendship.status = FriendshipStatus.accepted
        db.commit()
        
        return {"success": True, "message": "已接受好友请求"}
    
    @staticmethod
    def reject_friend_request(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        拒绝好友请求
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 发起者ID
        :return: 结果
        """
        # 查找待确认的好友请求
        friendship = db.query(Friendship).filter(
            Friendship.user_id == friend_id,
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.pending
        ).first()
        
        if not friendship:
            return {"success": False, "message": "好友请求不存在"}
        
        # 更新状态
        friendship.status = FriendshipStatus.rejected
        db.commit()
        
        return {"success": True, "message": "已拒绝好友请求"}
    
    @staticmethod
    def delete_friend(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        删除好友
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 好友ID
        :return: 结果
        """
        # 查找好友关系
        friendship = db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
            ),
            Friendship.status == FriendshipStatus.accepted
        ).first()
        
        if not friendship:
            return {"success": False, "message": "好友关系不存在"}
        
        # 删除好友关系
        db.delete(friendship)
        db.commit()
        
        return {"success": True, "message": "已删除好友"}
    
    @staticmethod
    def block_user(db: Session, user_id: int, friend_id: int) -> Dict:
        """
        拉黑用户
        :param db: 数据库会话
        :param user_id: 当前用户ID
        :param friend_id: 目标用户ID
        :return: 结果
        """
        # 查找好友关系
        friendship = db.query(Friendship).filter(
            or_(
                and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
                and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
            )
        ).first()
        
        if friendship:
            # 更新状态为拉黑
            friendship.status = FriendshipStatus.blocked
            friendship.user_id = user_id  # 确保是当前用户拉黑对方
            friendship.friend_id = friend_id
        else:
            # 创建拉黑记录
            friendship = Friendship(
                user_id=user_id,
                friend_id=friend_id,
                status=FriendshipStatus.blocked
            )
            db.add(friendship)
        
        db.commit()
        return {"success": True, "message": "已拉黑该用户"}
    
    @staticmethod
    def get_friend_list(db: Session, user_id: int) -> List[Dict]:
        """
        获取好友列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 好友列表
        """
        # 查询所有已接受的好友关系
        friendships = db.query(Friendship).filter(
            or_(
                Friendship.user_id == user_id,
                Friendship.friend_id == user_id
            ),
            Friendship.status == FriendshipStatus.accepted
        ).all()
        
        result = []
        for friendship in friendships:
            # 确定好友ID
            friend_id = friendship.friend_id if friendship.user_id == user_id else friendship.user_id
            
            # 获取好友信息
            friend = db.query(User).filter(User.id == friend_id).first()
            if friend:
                result.append({
                    "user_id": friend.id,
                    "username": friend.username,
                    "student_id": friend.student_id,
                    "school_id": friend.school_id,
                    "college_id": friend.college_id,
                    "major_id": friend.major_id,
                    "class_name": friend.class_name,
                    "friendship_since": friendship.created_at.isoformat()
                })
        
        return result
    
    @staticmethod
    def get_pending_requests(db: Session, user_id: int) -> List[Dict]:
        """
        获取待处理的好友请求
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 待处理请求列表
        """
        # 查询发给我的待确认请求
        friendships = db.query(Friendship).filter(
            Friendship.friend_id == user_id,
            Friendship.status == FriendshipStatus.pending
        ).all()
        
        result = []
        for friendship in friendships:
            # 获取发起者信息
            requester = db.query(User).filter(User.id == friendship.user_id).first()
            if requester:
                result.append({
                    "user_id": requester.id,
                    "username": requester.username,
                    "student_id": requester.student_id,
                    "school_id": requester.school_id,
                    "college_id": requester.college_id,
                    "major_id": requester.major_id,
                    "class_name": requester.class_name,
                    "requested_at": friendship.created_at.isoformat()
                })
        
        return result
