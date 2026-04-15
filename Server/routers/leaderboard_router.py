"""
排行榜路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
from database.db import get_default_db
from database.models import User
from services.leaderboard_service import LeaderboardService
from utils.redis_client import redis_client

router = APIRouter(prefix="/api/leaderboard", tags=["排行榜"])


class LeaderboardItem(BaseModel):
    """排行榜项"""
    rank: int
    user_id: int
    username: str
    student_id: str
    total_count: int
    correct_count: int
    wrong_count: int
    accuracy: float
    score: float


class PersonalStatsResponse(BaseModel):
    """个人统计响应"""
    user_id: int
    username: str
    student_id: str
    total_count: int
    correct_count: int
    wrong_count: int
    accuracy: float
    score: float
    ranks: Dict[str, int]


@router.get("/comprehensive", response_model=List[LeaderboardItem])
def get_comprehensive_leaderboard(
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取综合排行榜（所有用户）
    :param limit: 返回数量限制
    :param days: 统计天数（不传则统计全部）
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:comprehensive:limit:{limit}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [LeaderboardItem(**item) for item in cached_data]
    
    # 从数据库查询
    leaderboard = LeaderboardService.get_comprehensive_leaderboard(db, limit, days)
    
    # 存入缓存（10分钟）
    redis_client.set(cache_key, leaderboard, expire=600)
    
    return [LeaderboardItem(**item) for item in leaderboard]


@router.get("/school/{school_id}", response_model=List[LeaderboardItem])
def get_school_leaderboard(
    school_id: int,
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取校级排行榜（同一学校的用户）
    :param school_id: 学校ID
    :param limit: 返回数量限制
    :param days: 统计天数
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:school:{school_id}:limit:{limit}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [LeaderboardItem(**item) for item in cached_data]
    
    # 从数据库查询
    leaderboard = LeaderboardService.get_school_leaderboard(db, school_id, limit, days)
    
    # 存入缓存（10分钟）
    redis_client.set(cache_key, leaderboard, expire=600)
    
    return [LeaderboardItem(**item) for item in leaderboard]


@router.get("/college/{college_id}", response_model=List[LeaderboardItem])
def get_college_leaderboard(
    college_id: int,
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取院级排行榜（同一学院的用户）
    :param college_id: 学院ID
    :param limit: 返回数量限制
    :param days: 统计天数
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:college:{college_id}:limit:{limit}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [LeaderboardItem(**item) for item in cached_data]
    
    # 从数据库查询
    leaderboard = LeaderboardService.get_college_leaderboard(db, college_id, limit, days)
    
    # 存入缓存（10分钟）
    redis_client.set(cache_key, leaderboard, expire=600)
    
    return [LeaderboardItem(**item) for item in leaderboard]


@router.get("/major/{major_id}", response_model=List[LeaderboardItem])
def get_major_leaderboard(
    major_id: int,
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取专业排行榜（同一专业的用户）
    :param major_id: 专业ID
    :param limit: 返回数量限制
    :param days: 统计天数
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:major:{major_id}:limit:{limit}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [LeaderboardItem(**item) for item in cached_data]
    
    # 从数据库查询
    leaderboard = LeaderboardService.get_major_leaderboard(db, major_id, limit, days)
    
    # 存入缓存（10分钟）
    redis_client.set(cache_key, leaderboard, expire=600)
    
    return [LeaderboardItem(**item) for item in leaderboard]


@router.get("/class", response_model=List[LeaderboardItem])
def get_class_leaderboard(
    school_id: int = Query(...),
    college_id: int = Query(...),
    major_id: int = Query(...),
    class_name: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取班级排行榜（同一班级的用户）
    :param school_id: 学校ID
    :param college_id: 学院ID
    :param major_id: 专业ID
    :param class_name: 班级名称
    :param limit: 返回数量限制
    :param days: 统计天数
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:class:{school_id}:{college_id}:{major_id}:{class_name}:limit:{limit}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [LeaderboardItem(**item) for item in cached_data]
    
    # 从数据库查询
    leaderboard = LeaderboardService.get_class_leaderboard(
        db, school_id, college_id, major_id, class_name, limit, days
    )
    
    # 存入缓存（10分钟）
    redis_client.set(cache_key, leaderboard, expire=600)
    
    return [LeaderboardItem(**item) for item in leaderboard]


@router.get("/personal/{user_id}", response_model=PersonalStatsResponse)
def get_personal_stats(
    user_id: int,
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取个人统计数据和在各排行榜中的排名
    :param user_id: 用户ID
    :param days: 统计天数
    """
    # 尝试从缓存获取
    cache_key = f"leaderboard:personal:{user_id}:days:{days or 'all'}"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return PersonalStatsResponse(**cached_data)
    
    # 从数据库查询
    stats = LeaderboardService.get_personal_stats(db, user_id, days)
    
    if not stats:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 存入缓存（5分钟，个人数据更新频繁）
    redis_client.set(cache_key, stats, expire=300)
    
    return stats


@router.get("/user-leaderboards/{user_id}")
def get_user_leaderboards(
    user_id: int,
    limit: int = Query(100, ge=1, le=1000),
    days: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_default_db)
):
    """
    获取用户相关的所有排行榜数据（一次性返回）
    :param user_id: 用户ID
    :param limit: 每个排行榜的返回数量限制
    :param days: 统计天数
    """
    # 获取用户信息
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    result = {
        "comprehensive": LeaderboardService.get_comprehensive_leaderboard(db, limit, days),
        "personal": LeaderboardService.get_personal_stats(db, user_id, days)
    }
    
    # 根据用户信息添加相应的排行榜
    if user.school_id:
        result["school"] = LeaderboardService.get_school_leaderboard(
            db, user.school_id, limit, days
        )
    
    if user.college_id:
        result["college"] = LeaderboardService.get_college_leaderboard(
            db, user.college_id, limit, days
        )
    
    if user.major_id:
        result["major"] = LeaderboardService.get_major_leaderboard(
            db, user.major_id, limit, days
        )
    
    if all([user.school_id, user.college_id, user.major_id, user.class_name]):
        result["class"] = LeaderboardService.get_class_leaderboard(
            db, user.school_id, user.college_id, user.major_id, 
            user.class_name, limit, days
        )
    
    return result
