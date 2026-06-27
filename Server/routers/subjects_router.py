"""
科目路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database.db import get_default_db
from database.models import Subject, User
from services.share_service import ShareService
from utils.redis_client import redis_client, invalidate_cache

router = APIRouter(prefix="/api/subjects", tags=["科目管理"])


class SubjectCreate(BaseModel):
    """创建科目请求"""
    name: str
    user_id: int
    semester_id: Optional[int] = None


class SubjectUpdate(BaseModel):
    """更新科目请求"""
    name: Optional[str] = None
    semester_id: Optional[int] = None


class SubjectResponse(BaseModel):
    """科目响应"""
    id: int
    name: str
    user_id: int
    semester_id: Optional[int] = None
    created_at: str
    is_owner: bool = True
    is_shared: bool = False
    owner_username: Optional[str] = None
    share_type: Optional[str] = None
    has_shared: bool = False

    class Config:
        from_attributes = True


@router.post("/", response_model=SubjectResponse)
def create_subject(subject: SubjectCreate, db: Session = Depends(get_default_db)):
    """创建科目"""
    # 检查是否已存在
    existing = db.query(Subject).filter(
        Subject.user_id == subject.user_id,
        Subject.name == subject.name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该科目已存在")
    
    # 获取用户的组织架构信息
    user = db.query(User).filter(User.id == subject.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 创建科目，自动继承用户的组织架构信息
    db_subject = Subject(
        user_id=subject.user_id,
        name=subject.name,
        school_id=user.school_id,
        college_id=user.college_id,
        major_id=user.major_id,
        semester_id=subject.semester_id,
        visibility_level='private'
    )
    
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    
    # 清除用户科目列表缓存
    invalidate_cache(f"subjects:user:{subject.user_id}:*")
    
    return SubjectResponse(
        id=db_subject.id,
        name=db_subject.name,
        user_id=db_subject.user_id,
        semester_id=db_subject.semester_id,
        created_at=db_subject.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )


@router.get("/", response_model=List[SubjectResponse])
def get_subjects(user_id: int, db: Session = Depends(get_default_db)):
    """获取用户的所有科目（包含共享科目）"""
    # 尝试从缓存获取
    cache_key = f"subjects:user:{user_id}:list"
    cached_data = redis_client.get(cache_key)
    
    if cached_data is not None:
        return [SubjectResponse(**s) for s in cached_data]
    
    # 使用ShareService获取可访问的科目（自己的+共享的）
    subjects = ShareService.get_accessible_subjects(user_id, db)
    
    # 存入缓存（5分钟）
    redis_client.set(cache_key, subjects, expire=300)
    
    return [SubjectResponse(**s) for s in subjects]


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(subject_id: int, user_id: int, db: Session = Depends(get_default_db)):
    """获取单个科目"""
    subject = db.query(Subject).filter(
        Subject.id == subject_id,
        Subject.user_id == user_id
    ).first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    
    return SubjectResponse(
        id=subject.id,
        name=subject.name,
        user_id=subject.user_id,
        semester_id=subject.semester_id,
        created_at=subject.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )


@router.put("/{subject_id}", response_model=SubjectResponse)
def update_subject(subject_id: int, body: SubjectUpdate, user_id: int, db: Session = Depends(get_default_db)):
    """更新科目（名称 / 学期）"""
    from services.share_service import ShareService
    if not ShareService.can_edit_subject(user_id, subject_id, db):
        raise HTTPException(status_code=403, detail="无权编辑此科目")

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")

    if body.name is not None:
        subject.name = body.name.strip()
    if body.semester_id is not None:
        subject.semester_id = body.semester_id
    elif body.semester_id == 0:        # 传 0 表示清空学期
        subject.semester_id = None

    db.commit()
    db.refresh(subject)
    invalidate_cache(f"subjects:user:{user_id}:*")

    return SubjectResponse(
        id=subject.id,
        name=subject.name,
        user_id=subject.user_id,
        semester_id=subject.semester_id,
        created_at=subject.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )


@router.delete("/{subject_id}")
def delete_subject(subject_id: int, user_id: int, db: Session = Depends(get_default_db)):
    """删除科目（仅拥有者可删除）
    
    删除科目将会级联删除：
    - 该科目下的所有题目
    - 该科目的所有练习会话（试卷）
    - 该科目的所有练习记录（答题记录）
    - 该科目的所有错题记录
    - 该科目的所有共享记录
    """
    # 使用ShareService检查编辑权限
    if not ShareService.can_edit_subject(user_id, subject_id, db):
        raise HTTPException(status_code=403, detail="无权删除此科目")
    
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在")
    
    subject_name = subject.name
    
    # 删除科目（数据库级联会自动删除关联数据）
    db.delete(subject)
    db.commit()
    
    # 清除所有相关缓存
    invalidate_cache(f"subjects:user:{user_id}:*")
    invalidate_cache(f"subjects:user:*")  # 清除所有用户的科目列表缓存（如果有共享）
    invalidate_cache(f"subject:{subject_id}:*")
    invalidate_cache(f"questions:subject:{subject_id}:*")
    invalidate_cache(f"practice:user:{user_id}:*")  # 清除练习相关缓存
    invalidate_cache(f"error:user:{user_id}:*")  # 清除错题集缓存
    invalidate_cache(f"shares:subject:{subject_id}:*")  # 清除共享记录缓存
    
    return {
        "message": "科目删除成功",
        "detail": f"科目「{subject_name}」及其所有关联数据已删除"
    }
