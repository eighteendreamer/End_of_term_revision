"""
个人信息管理路由
所有接口通过 JWT token 鉴权，user_id 从 token 中提取（防止 IDOR）
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from database.db import get_default_db
from database.models import User, School, College, Major
from utils.redis_client import redis_client
from utils.security import get_current_user_id, validate_safe_input
import bcrypt

router = APIRouter(prefix="/api/profile", tags=["个人信息"])


class UpdateProfileBody(BaseModel):
    """更新个人信息请求体"""
    username: Optional[str] = Field(None, min_length=2, max_length=255)
    school_id: Optional[int] = None
    college_id: Optional[int] = None
    major_id: Optional[int] = None
    class_name: Optional[str] = Field(None, max_length=100)


class ChangePasswordBody(BaseModel):
    """修改密码请求体"""
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=255)


@router.get("/me")
def get_profile(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_default_db)
):
    """
    获取个人信息（user_id 从 token 中提取，防止越权）
    """
    user = db.query(User).filter(User.id == current_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 查询学校/学院/专业名称
    school_name = None
    college_name = None
    major_name = None
    
    if user.school_id:
        school = db.query(School).filter(School.id == user.school_id).first()
        school_name = school.name if school else None
    
    if user.college_id:
        college = db.query(College).filter(College.id == user.college_id).first()
        college_name = college.name if college else None
    
    if user.major_id:
        major = db.query(Major).filter(Major.id == user.major_id).first()
        major_name = major.name if major else None
    
    return {
        "code": 200,
        "message": "获取成功",
        "data": {
            "user_id": user.id,
            "username": user.username,
            "student_id": user.student_id,
            "school_id": user.school_id,
            "college_id": user.college_id,
            "major_id": user.major_id,
            "school_name": school_name,
            "college_name": college_name,
            "major_name": major_name,
            "class_name": user.class_name,
            "gender": user.gender.value if user.gender else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        }
    }


@router.put("/update")
def update_profile(
    body: UpdateProfileBody,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_default_db)
):
    """
    更新个人信息（user_id 从 token 中提取，防止越权）
    """
    user = db.query(User).filter(User.id == current_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新字段（带输入清洗）
    if body.username is not None:
        clean_name = validate_safe_input(body.username, "用户名")
        existing = db.query(User).filter(
            User.username == clean_name,
            User.id != current_user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="用户名已存在")
        user.username = clean_name
    
    if body.school_id is not None:
        user.school_id = body.school_id
    if body.college_id is not None:
        user.college_id = body.college_id
    if body.major_id is not None:
        user.major_id = body.major_id
    if body.class_name is not None:
        user.class_name = validate_safe_input(body.class_name, "班级")
    
    db.commit()
    db.refresh(user)
    
    redis_client.delete(f"user:profile:{current_user_id}")
    redis_client.delete_pattern(f"leaderboard:*")
    
    return {
        "code": 200,
        "message": "更新成功",
        "data": {
            "user_id": user.id,
            "username": user.username,
            "student_id": user.student_id,
            "school_id": user.school_id,
            "college_id": user.college_id,
            "major_id": user.major_id,
            "class_name": user.class_name
        }
    }


@router.post("/change-password")
def change_password(
    body: ChangePasswordBody,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_default_db)
):
    """
    修改密码（user_id 从 token 中提取，旧密码用 bcrypt 验证）
    """
    user = db.query(User).filter(User.id == current_user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 用 bcrypt 验证旧密码
    try:
        if not bcrypt.checkpw(body.old_password.encode('utf-8'), user.password_hash.encode('utf-8')):
            raise HTTPException(status_code=400, detail="旧密码错误")
    except Exception:
        raise HTTPException(status_code=400, detail="旧密码错误")
    
    # 用 bcrypt 加密新密码
    salt = bcrypt.gensalt()
    user.password_hash = bcrypt.hashpw(body.new_password.encode('utf-8'), salt).decode('utf-8')
    db.commit()
    
    return {
        "code": 200,
        "message": "密码修改成功",
        "data": None
    }
