"""
聊天系统路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from database.db import get_default_db
from services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["聊天系统"])


class SendMessageBody(BaseModel):
    """发送消息请求体"""
    to_user_id: int
    content: str
    message_type: str = "text"


@router.post("/send")
def send_message(
    body: SendMessageBody,
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    发送消息
    :param body: 消息内容
    :param current_user_id: 当前用户ID
    """
    result = ChatService.send_message(
        db,
        from_user_id=current_user_id,
        to_user_id=body.to_user_id,
        content=body.content,
        message_type=body.message_type
    )
    
    if not result.get("success", True):
        raise HTTPException(status_code=400, detail=result["message"])
    
    return {
        "code": 200,
        "message": "发送成功",
        "data": result
    }


@router.get("/history")
def get_chat_history(
    friend_id: int = Query(...),
    current_user_id: int = Query(...),
    limit: int = Query(50, ge=1, le=100),
    before_message_id: Optional[int] = Query(None),
    db: Session = Depends(get_default_db)
):
    """
    获取聊天历史
    :param friend_id: 好友ID
    :param current_user_id: 当前用户ID
    :param limit: 返回数量
    :param before_message_id: 在此消息之前的消息（用于分页）
    """
    messages = ChatService.get_chat_history(
        db,
        user_id=current_user_id,
        friend_id=friend_id,
        limit=limit,
        before_message_id=before_message_id
    )
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": messages
    }


@router.post("/mark-read")
def mark_as_read(
    friend_id: int = Query(...),
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    标记消息为已读
    :param friend_id: 好友ID
    :param current_user_id: 当前用户ID
    """
    result = ChatService.mark_as_read(db, current_user_id, friend_id)
    
    return {
        "code": 200,
        "message": "标记成功",
        "data": result
    }


@router.get("/unread-count")
def get_unread_count(
    current_user_id: int = Query(...),
    friend_id: Optional[int] = Query(None),
    db: Session = Depends(get_default_db)
):
    """
    获取未读消息数
    :param current_user_id: 当前用户ID
    :param friend_id: 好友ID（可选）
    """
    count = ChatService.get_unread_count(db, current_user_id, friend_id)
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": {"count": count}
    }


@router.get("/conversations")
def get_conversation_list(
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    获取会话列表（最近联系人）
    :param current_user_id: 当前用户ID
    """
    conversations = ChatService.get_conversation_list(db, current_user_id)
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": conversations
    }
