"""
用户认证路由模块
提供用户注册、登录、获取当前用户信息等功能
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
import bcrypt
import jwt
import hashlib
import logging

from database.db import get_default_db
from database.models import User, GenderType, School, College, Major
from middleware.security_middleware import SecurityMiddleware

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["用户认证"])

# JWT配置（使用集中管理的密钥）
from utils.security import JWT_SECRET_KEY as SECRET_KEY, JWT_ALGORITHM as ALGORITHM, JWT_EXPIRE_MINUTES as ACCESS_TOKEN_EXPIRE_MINUTES
from utils.security import create_token, decode_token as _decode_token, validate_safe_input

# 请求/响应模型
class RegisterRequest(BaseModel):
    student_id: str = Field(..., min_length=1, max_length=50, description="学号（唯一）")
    username: str = Field(..., min_length=2, max_length=255, description="用户名")
    password_md5: str = Field(..., description="前端MD5加密后的密码")
    school: Optional[str] = Field(None, max_length=255, description="学校")
    college: Optional[str] = Field(None, max_length=255, description="二级学院（可选）")
    major: Optional[str] = Field(None, max_length=255, description="专业（可选）")
    class_name: Optional[str] = Field(None, max_length=100, description="班级")
    gender: Optional[str] = Field(None, description="性别：male=男，female=女，hidden=隐藏")


class LoginRequest(BaseModel):
    student_id: Optional[str] = Field(None, description="学号（新用户）")
    username: Optional[str] = Field(None, description="用户名（内测用户兼容）")
    password_md5: str = Field(..., description="前端MD5加密后的密码")


class UpdateProfileRequest(BaseModel):
    student_id: Optional[str] = Field(None, min_length=1, max_length=50, description="学号（内测用户必须填写）")
    username: Optional[str] = Field(None, min_length=2, max_length=255, description="用户名")
    password_md5: Optional[str] = Field(None, description="新密码（MD5加密，内测用户必须设置）")
    school: Optional[str] = Field(None, max_length=255, description="学校")
    college: Optional[str] = Field(None, max_length=255, description="二级学院（可选）")
    major: Optional[str] = Field(None, max_length=255, description="专业（可选）")
    class_name: Optional[str] = Field(None, max_length=100, description="班级")
    gender: Optional[str] = Field(None, description="性别：male=男，female=女，hidden=隐藏")


class UserResponse(BaseModel):
    id: int
    student_id: str
    username: str
    school_id: Optional[int]  # 改为 school_id
    college_id: Optional[int]  # 改为 college_id
    major_id: Optional[int]  # 改为 major_id
    class_name: Optional[str]
    gender: Optional[str]
    profile_completed: int
    created_at: datetime


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    profile_completed: int
    message: Optional[str] = None


def md5_to_bcrypt(md5_password: str) -> str:
    """
    将前端MD5加密的密码转换为bcrypt加密存储
    
    流程：
    1. 前端：用户密码 → MD5加密 → 发送到后端
    2. 后端：接收MD5密码 → bcrypt加密 → 存储到数据库
    
    注意：MD5是单向哈希，不可逆，这里不是"解密"MD5
    而是把MD5值作为输入，再用bcrypt加密一次
    
    Args:
        md5_password: 前端MD5加密后的密码（32位十六进制字符串）
    
    Returns:
        bcrypt加密后的密码哈希值
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(md5_password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_md5_password(md5_password: str, bcrypt_hash: str) -> bool:
    """
    验证MD5密码
    
    流程：
    1. 前端：用户输入密码 → MD5加密 → 发送到后端
    2. 后端：接收MD5密码 → 用bcrypt验证存储的哈希值
    
    适用于：
    - 新用户：密码 → MD5 → bcrypt存储
    - 内测用户：密码 → MD5 → bcrypt存储（相同方式）
    
    Args:
        md5_password: 前端MD5加密后的密码
        bcrypt_hash: 数据库中存储的bcrypt哈希值
    
    Returns:
        密码是否匹配
    """
    try:
        return bcrypt.checkpw(md5_password.encode('utf-8'), bcrypt_hash.encode('utf-8'))
    except:
        return False


def check_profile_completed(user: User) -> bool:
    """
    检查用户信息是否完善
    必填项：学号、用户名、密码、学校ID、班级、性别
    可选项：学院ID、专业ID
    """
    required_fields = [
        user.student_id,
        user.username,
        user.password_hash,
        user.school_id,  # 改为使用 school_id
        user.class_name,
        user.gender
    ]
    return all(field is not None and str(field).strip() != '' for field in required_fields)


def create_access_token(data: dict) -> str:
    """创建JWT token（使用集中管理的密钥）"""
    return create_token(data)


def decode_token(token: str) -> dict:
    """解码JWT token（使用集中管理的密钥）"""
    return _decode_token(token)


def get_user_response(user: User) -> dict:
    """构建用户响应数据"""
    return {
        "id": user.id,
        "student_id": user.student_id,
        "username": user.username,
        "school_id": user.school_id,
        "college_id": user.college_id,
        "major_id": user.major_id,
        "class_name": user.class_name,
        "gender": user.gender.value if user.gender else None,
        "profile_completed": user.profile_completed,
        "created_at": user.created_at
    }


def get_or_create_school(db: Session, school_name: str) -> int:
    """
    获取或创建学校记录
    
    Args:
        db: 数据库会话
        school_name: 学校名称
    
    Returns:
        学校ID
    """
    if not school_name or school_name.strip() == '':
        pass  # debug removed
        return None
    
    # 查找现有学校
    school = db.query(School).filter(School.name == school_name).first()
    
    if school:
        pass  # debug removed
        return school.id
    
    # 创建新学校
    new_school = School(name=school_name)
    db.add(new_school)
    db.flush()  # 获取ID但不提交事务
    pass  # debug removed
    
    return new_school.id


def get_or_create_college(db: Session, school_id: int, college_name: str) -> int:
    """
    获取或创建学院记录
    
    Args:
        db: 数据库会话
        school_id: 学校ID
        college_name: 学院名称
    
    Returns:
        学院ID
    """
    if not college_name or college_name.strip() == '' or not school_id:
        pass  # debug removed
        return None
    
    # 查找现有学院
    college = db.query(College).filter(
        College.school_id == school_id,
        College.name == college_name
    ).first()
    
    if college:
        pass  # debug removed
        return college.id
    
    # 创建新学院
    new_college = College(
        school_id=school_id,
        name=college_name
    )
    db.add(new_college)
    db.flush()  # 获取ID但不提交事务
    pass  # debug removed
    
    return new_college.id


def get_or_create_major(db: Session, school_id: int, college_id: int, major_name: str) -> int:
    """
    获取或创建专业记录
    
    Args:
        db: 数据库会话
        school_id: 学校ID
        college_id: 学院ID
        major_name: 专业名称
    
    Returns:
        专业ID
    """
    if not major_name or major_name.strip() == '' or not college_id or not school_id:
        return None
    
    # 查找现有专业
    major = db.query(Major).filter(
        Major.college_id == college_id,
        Major.name == major_name
    ).first()
    
    if major:
        pass  # debug removed
        return major.id
    
    # 创建新专业
    new_major = Major(
        college_id=college_id,
        school_id=school_id,
        name=major_name
    )
    db.add(new_major)
    db.flush()  # 获取ID但不提交事务
    pass  # debug removed
    
    return new_major.id


@router.post("/register", response_model=LoginResponse, summary="用户注册")
def register(request: RegisterRequest, db: Session = Depends(get_default_db)):
    """
    用户注册接口
    - 检查学号是否已存在
    - 前端发送MD5加密的密码，后端转bcrypt加密存储
    - 返回JWT token和用户信息
    - 检查账号信息是否完善
    """
    # 检查学号是否已存在
    existing_user = db.query(User).filter(User.student_id == request.student_id).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="学号已存在"
        )
    
    # 验证性别枚举值
    gender_enum = None
    if request.gender:
        try:
            gender_enum = GenderType(request.gender)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="性别值无效，必须是 male、female 或 hidden"
            )
    
    # 将MD5密码转换为bcrypt加密
    bcrypt_hash = md5_to_bcrypt(request.password_md5)
    
    # 处理组织架构信息（获取或创建学校、学院、专业）
    school_id = None
    college_id = None
    major_id = None
    
    pass  # debug removed
    
    if request.school:
        school_id = get_or_create_school(db, request.school)
        pass  # debug removed
        
        if request.college and school_id:
            college_id = get_or_create_college(db, school_id, request.college)
            pass  # debug removed
            
            if request.major and college_id:
                major_id = get_or_create_major(db, school_id, college_id, request.major)
                pass  # debug removed
    
    # 创建新用户
    new_user = User(
        student_id=request.student_id,
        username=request.username,
        password_hash=bcrypt_hash,
        school_id=school_id,
        college_id=college_id,
        major_id=major_id,
        class_name=request.class_name,
        gender=gender_enum,
        profile_completed=0  # 初始为未完善
    )
    
    # 检查信息是否完善
    is_completed = check_profile_completed(new_user)
    new_user.profile_completed = 1 if is_completed else 0
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 生成token
    token = create_access_token({
        "user_id": new_user.id,
        "student_id": new_user.student_id,
        "username": new_user.username
    })
    
    message = None if is_completed else "请完善账号信息：学校、班级、性别为必填项"
    
    return {
        "token": token,
        "user": get_user_response(new_user),
        "profile_completed": new_user.profile_completed,
        "message": message
    }


@router.post("/login", response_model=LoginResponse, summary="用户登录")
def login(request_data: LoginRequest, request: Request, db: Session = Depends(get_default_db)):
    """
    用户登录接口
    - 支持学号+密码登录（新用户）
    - 支持用户名+密码登录（内测用户兼容）
    - 内测用户（profile_completed=0）使用用户名登录时，不验证密码，直接返回需要完善信息
    - 前端发送MD5加密的密码，后端验证bcrypt
    - 返回JWT token和用户信息
    """
    # 获取客户端IP
    client_ip = SecurityMiddleware.get_client_ip(request)
    
    # 验证登录凭证
    if not request_data.student_id and not request_data.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供学号或用户名"
        )
    
    login_identifier = request_data.student_id or request_data.username
    
    # 检查账号是否被锁定（暴力破解防护）
    if SecurityMiddleware.is_account_locked(client_ip, login_identifier):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，账号已暂时锁定，请15分钟后再试"
        )
    
    # 查找用户（优先使用学号，兼容用户名）
    user = None
    is_username_login = False
    
    if request_data.student_id:
        user = db.query(User).filter(User.student_id == request_data.student_id).first()
    elif request_data.username:
        user = db.query(User).filter(User.username == request_data.username).first()
        is_username_login = True
    
    if not user:
        # 记录失败的登录尝试
        SecurityMiddleware.record_failed_login(client_ip, login_identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号/用户名或密码错误"
        )
    
    pass  # debug removed
    
    # 特殊处理：内测用户使用用户名登录且信息未完善
    if is_username_login and user.profile_completed == 0:
        pass  # debug removed
        
        # 生成临时token（用于完善信息）
        token = create_access_token({
            "user_id": user.id,
            "student_id": user.student_id,
            "username": user.username,
            "temp": True  # 标记为临时token
        })
        
        return {
            "token": token,
            "user": get_user_response(user),
            "profile_completed": 0,
            "message": "内测用户首次登录，请完善账号信息"
        }
    
    # 正常登录流程：验证密码
    pass  # debug removed
    pass  # debug removed
    
    password_valid = verify_md5_password(request_data.password_md5, user.password_hash)
    pass  # debug removed
    
    if not password_valid:
        # 记录失败的登录尝试
        SecurityMiddleware.record_failed_login(client_ip, login_identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="学号/用户名或密码错误"
        )
    
    # 检查信息是否完善
    is_completed = check_profile_completed(user)
    
    # 如果信息已完善但状态未更新，更新状态
    if is_completed and user.profile_completed == 0:
        user.profile_completed = 1
        db.commit()
        db.refresh(user)
    
    # 生成token
    token = create_access_token({
        "user_id": user.id,
        "student_id": user.student_id,
        "username": user.username
    })
    
    return {
        "token": token,
        "user": get_user_response(user),
        "profile_completed": user.profile_completed,
        "message": None
    }


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
def get_current_user(token: str, db: Session = Depends(get_default_db)):
    """
    获取当前登录用户信息
    - 需要在请求头中提供token
    """
    # 解码token
    payload = decode_token(token)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的token")
    
    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return get_user_response(user)


@router.put("/profile", response_model=UserResponse, summary="完善/更新用户信息")
def update_profile(
    request: UpdateProfileRequest,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    完善或更新用户信息
    - 需要在请求头中提供token
    - 可以更新：学号、用户名、密码、学校、二级学院、专业、班级、性别
    - 自动检查信息是否完善并更新状态
    - 内测用户首次完善时必须填写学号和设置新密码
    """
    # 解码token
    payload = decode_token(token)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的token")
    
    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 更新学号（如果提供）
    if request.student_id is not None:
        # 检查学号是否已被其他用户使用
        existing_user = db.query(User).filter(
            User.student_id == request.student_id,
            User.id != user_id
        ).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该学号已被使用"
            )
        user.student_id = request.student_id
    
    # 更新密码（如果提供）
    if request.password_md5 is not None:
        # 将MD5密码转换为bcrypt加密
        user.password_hash = md5_to_bcrypt(request.password_md5)
    
    # 处理组织架构信息（获取或创建学校、学院、专业）
    pass  # debug removed
    
    if request.school is not None:
        school_id = get_or_create_school(db, request.school)
        user.school_id = school_id
        pass  # debug removed
        
        if request.college is not None and school_id:
            college_id = get_or_create_college(db, school_id, request.college)
            user.college_id = college_id
            pass  # debug removed
            
            if request.major is not None and college_id:
                major_id = get_or_create_major(db, school_id, college_id, request.major)
                user.major_id = major_id
                pass  # debug removed
    
    # 更新其他字段
    if request.username is not None:
        user.username = request.username
    if request.class_name is not None:
        user.class_name = request.class_name
    if request.gender is not None:
        try:
            user.gender = GenderType(request.gender)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="性别值无效，必须是 male、female 或 hidden"
            )
    
    # 检查信息是否完善
    is_completed = check_profile_completed(user)
    user.profile_completed = 1 if is_completed else 0
    
    db.commit()
    db.refresh(user)
    
    return get_user_response(user)


@router.get("/check-profile", summary="检查账号信息是否完善")
def check_profile(token: str, db: Session = Depends(get_default_db)):
    """
    检查当前用户账号信息是否完善
    - 返回完善状态和缺失的必填项
    """
    # 解码token
    payload = decode_token(token)
    user_id = payload.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的token")
    
    # 查询用户
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 检查各个必填项
    missing_fields = []
    if not user.school_id:  # 改为检查 school_id
        missing_fields.append("学校")
    if not user.class_name or user.class_name.strip() == '':
        missing_fields.append("班级")
    if not user.gender:
        missing_fields.append("性别")
    
    is_completed = len(missing_fields) == 0
    
    return {
        "profile_completed": 1 if is_completed else 0,
        "is_completed": is_completed,
        "missing_fields": missing_fields,
        "message": "账号信息完整" if is_completed else f"请完善以下信息：{', '.join(missing_fields)}"
    }


@router.post("/logout", summary="用户登出")
def logout():
    """
    用户登出接口
    - 前端需要删除本地存储的token
    """
    return {"message": "登出成功"}
