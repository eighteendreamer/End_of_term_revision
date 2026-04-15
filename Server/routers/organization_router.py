"""
组织架构管理路由模块
提供学校、学院、专业、课程的CRUD操作
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from database.db import get_default_db
from database.models import School, College, Major
from routers.auth_router import decode_token

router = APIRouter(prefix="/api/organization", tags=["组织架构管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class SchoolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="学校名称")
    code: Optional[str] = Field(None, max_length=50, description="学校代码")
    province: Optional[str] = Field(None, max_length=50, description="省份")
    city: Optional[str] = Field(None, max_length=50, description="城市")


class SchoolResponse(BaseModel):
    id: int
    name: str
    code: Optional[str]
    province: Optional[str]
    city: Optional[str]
    created_at: datetime


class CollegeCreate(BaseModel):
    school_id: int = Field(..., description="所属学校ID")
    name: str = Field(..., min_length=1, max_length=255, description="学院名称")
    code: Optional[str] = Field(None, max_length=50, description="学院代码")


class CollegeResponse(BaseModel):
    id: int
    school_id: int
    name: str
    code: Optional[str]
    created_at: datetime


class MajorCreate(BaseModel):
    college_id: int = Field(..., description="所属学院ID")
    school_id: int = Field(..., description="所属学校ID")
    name: str = Field(..., min_length=1, max_length=255, description="专业名称")
    code: Optional[str] = Field(None, max_length=50, description="专业代码")


class MajorResponse(BaseModel):
    id: int
    college_id: int
    school_id: int
    name: str
    code: Optional[str]
    created_at: datetime


# ============================================================
# 学校管理
# ============================================================

@router.get("/schools", response_model=List[SchoolResponse], summary="获取学校列表")
def get_schools(
    search: Optional[str] = None,
    province: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    获取学校列表
    - 支持按名称搜索
    - 支持按省份筛选
    """
    query = db.query(School)
    
    if search:
        query = query.filter(School.name.like(f"%{search}%"))
    
    if province:
        query = query.filter(School.province == province)
    
    schools = query.order_by(School.name).all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "province": s.province,
            "city": s.city,
            "created_at": s.created_at
        }
        for s in schools
    ]


@router.post("/schools", response_model=SchoolResponse, summary="创建学校")
def create_school(
    request: SchoolCreate,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    创建学校
    - 需要管理员权限（暂时允许所有登录用户）
    """
    # 验证token
    decode_token(token)
    
    # 检查学校名称是否已存在
    existing = db.query(School).filter(School.name == request.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="学校名称已存在"
        )
    
    # 创建学校
    school = School(
        name=request.name,
        code=request.code,
        province=request.province,
        city=request.city
    )
    
    db.add(school)
    db.commit()
    db.refresh(school)
    
    return {
        "id": school.id,
        "name": school.name,
        "code": school.code,
        "province": school.province,
        "city": school.city,
        "created_at": school.created_at
    }


# ============================================================
# 学院管理
# ============================================================

@router.get("/colleges", response_model=List[CollegeResponse], summary="获取学院列表")
def get_colleges(
    school_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    获取学院列表
    - 支持按学校筛选
    - 支持按名称搜索
    """
    query = db.query(College)
    
    if school_id:
        query = query.filter(College.school_id == school_id)
    
    if search:
        query = query.filter(College.name.like(f"%{search}%"))
    
    colleges = query.order_by(College.name).all()
    
    return [
        {
            "id": c.id,
            "school_id": c.school_id,
            "name": c.name,
            "code": c.code,
            "created_at": c.created_at
        }
        for c in colleges
    ]


@router.post("/colleges", response_model=CollegeResponse, summary="创建学院")
def create_college(
    request: CollegeCreate,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    创建学院
    - 需要管理员权限（暂时允许所有登录用户）
    """
    # 验证token
    decode_token(token)
    
    # 检查学校是否存在
    school = db.query(School).filter(School.id == request.school_id).first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学校不存在"
        )
    
    # 检查学院名称在该学校下是否已存在
    existing = db.query(College).filter(
        College.school_id == request.school_id,
        College.name == request.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该学校下已存在同名学院"
        )
    
    # 创建学院
    college = College(
        school_id=request.school_id,
        name=request.name,
        code=request.code
    )
    
    db.add(college)
    db.commit()
    db.refresh(college)
    
    return {
        "id": college.id,
        "school_id": college.school_id,
        "name": college.name,
        "code": college.code,
        "created_at": college.created_at
    }


# ============================================================
# 专业管理
# ============================================================

@router.get("/majors", response_model=List[MajorResponse], summary="获取专业列表")
def get_majors(
    school_id: Optional[int] = None,
    college_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    获取专业列表
    - 支持按学校筛选
    - 支持按学院筛选
    - 支持按名称搜索
    """
    query = db.query(Major)
    
    if school_id:
        query = query.filter(Major.school_id == school_id)
    
    if college_id:
        query = query.filter(Major.college_id == college_id)
    
    if search:
        query = query.filter(Major.name.like(f"%{search}%"))
    
    majors = query.order_by(Major.name).all()
    
    return [
        {
            "id": m.id,
            "college_id": m.college_id,
            "school_id": m.school_id,
            "name": m.name,
            "code": m.code,
            "created_at": m.created_at
        }
        for m in majors
    ]


@router.post("/majors", response_model=MajorResponse, summary="创建专业")
def create_major(
    request: MajorCreate,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    创建专业
    - 需要管理员权限（暂时允许所有登录用户）
    """
    # 验证token
    decode_token(token)
    
    # 检查学院是否存在
    college = db.query(College).filter(College.id == request.college_id).first()
    if not college:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学院不存在"
        )
    
    # 检查学校是否存在
    school = db.query(School).filter(School.id == request.school_id).first()
    if not school:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="学校不存在"
        )
    
    # 检查专业名称在该学院下是否已存在
    existing = db.query(Major).filter(
        Major.college_id == request.college_id,
        Major.name == request.name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该学院下已存在同名专业"
        )
    
    # 创建专业
    major = Major(
        college_id=request.college_id,
        school_id=request.school_id,
        name=request.name,
        code=request.code
    )
    
    db.add(major)
    db.commit()
    db.refresh(major)
    
    return {
        "id": major.id,
        "college_id": major.college_id,
        "school_id": major.school_id,
        "name": major.name,
        "code": major.code,
        "created_at": major.created_at
    }
