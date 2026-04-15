"""
好友系统路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from database.db import get_default_db
from services.friendship_service import FriendshipService
from utils.redis_client import redis_client

router = APIRouter(prefix="/api/friends", tags=["好友系统"])


class FriendRequestBody(BaseModel):
    """好友请求体"""
    friend_id: int


@router.get("/search")
def search_users(
    student_id: str = Query(..., min_length=1),
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    通过学号搜索用户
    :param student_id: 学号（支持模糊搜索）
    :param current_user_id: 当前用户ID
    """
    users = FriendshipService.search_users_by_student_id(db, student_id, current_user_id)
    return {
        "code": 200,
        "message": "搜索成功",
        "data": users
    }


@router.post("/request")
def send_friend_request(
    body: FriendRequestBody,
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    发送好友请求
    :param body: 请求体
    :param current_user_id: 当前用户ID
    """
    if body.friend_id == current_user_id:
        raise HTTPException(status_code=400, detail="不能添加自己为好友")
    
    result = FriendshipService.send_friend_request(db, current_user_id, body.friend_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    # 清除缓存
    redis_client.delete(f"friends:list:{current_user_id}")
    redis_client.delete(f"friends:pending:{body.friend_id}")
    
    return {
        "code": 200,
        "message": result["message"],
        "data": None
    }


@router.post("/accept")
def accept_friend_request(
    body: FriendRequestBody,
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    接受好友请求
    :param body: 请求体
    :param current_user_id: 当前用户ID
    """
    result = FriendshipService.accept_friend_request(db, current_user_id, body.friend_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    # 清除缓存
    redis_client.delete(f"friends:list:{current_user_id}")
    redis_client.delete(f"friends:list:{body.friend_id}")
    redis_client.delete(f"friends:pending:{current_user_id}")
    
    return {
        "code": 200,
        "message": result["message"],
        "data": None
    }


@router.post("/reject")
def reject_friend_request(
    body: FriendRequestBody,
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    拒绝好友请求
    :param body: 请求体
    :param current_user_id: 当前用户ID
    """
    result = FriendshipService.reject_friend_request(db, current_user_id, body.friend_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    # 清除缓存
    redis_client.delete(f"friends:pending:{current_user_id}")
    
    return {
        "code": 200,
        "message": result["message"],
        "data": None
    }


@router.delete("/delete")
def delete_friend(
    friend_id: int = Query(...),
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    删除好友
    :param friend_id: 好友ID
    :param current_user_id: 当前用户ID
    """
    result = FriendshipService.delete_friend(db, current_user_id, friend_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    # 清除缓存
    redis_client.delete(f"friends:list:{current_user_id}")
    redis_client.delete(f"friends:list:{friend_id}")
    
    return {
        "code": 200,
        "message": result["message"],
        "data": None
    }


@router.post("/block")
def block_user(
    body: FriendRequestBody,
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    拉黑用户
    :param body: 请求体
    :param current_user_id: 当前用户ID
    """
    result = FriendshipService.block_user(db, current_user_id, body.friend_id)
    
    # 清除缓存
    redis_client.delete(f"friends:list:{current_user_id}")
    redis_client.delete(f"friends:list:{body.friend_id}")
    
    return {
        "code": 200,
        "message": result["message"],
        "data": None
    }


@router.get("/list")
def get_friend_list(
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    获取好友列表
    :param current_user_id: 当前用户ID
    """
    # 尝试从缓存获取
    cache_key = f"friends:list:{current_user_id}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return {
            "code": 200,
            "message": "获取成功",
            "data": cached_data
        }
    
    # 从数据库查询
    friends = FriendshipService.get_friend_list(db, current_user_id)
    
    # 存入缓存（5分钟）
    redis_client.set(cache_key, friends, expire=300)
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": friends
    }


@router.get("/pending")
def get_pending_requests(
    current_user_id: int = Query(...),
    db: Session = Depends(get_default_db)
):
    """
    获取待处理的好友请求
    :param current_user_id: 当前用户ID
    """
    # 尝试从缓存获取
    cache_key = f"friends:pending:{current_user_id}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return {
            "code": 200,
            "message": "获取成功",
            "data": cached_data
        }
    
    # 从数据库查询
    requests = FriendshipService.get_pending_requests(db, current_user_id)
    
    # 存入缓存（1分钟，好友请求更新频繁）
    redis_client.set(cache_key, requests, expire=60)
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": requests
    }
