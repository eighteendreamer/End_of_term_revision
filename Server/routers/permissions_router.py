"""
权限管理路由模块
提供数据访问权限的授予、撤销、查询功能
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from database.db import get_default_db
from database.models import (
    User, Subject, Question,
    DataAccessPermission,
    PermissionLevel, ResourceType, VisibilityLevel
)
from routers.auth_router import decode_token

router = APIRouter(prefix="/api/permissions", tags=["权限管理"])


# ============================================================
# 请求/响应模型
# ============================================================

class GrantPermissionRequest(BaseModel):
    user_id: int = Field(..., description="被授权用户ID")
    resource_type: str = Field(..., description="资源类型：subject/question")
    resource_id: int = Field(..., description="资源ID")
    permission_level: str = Field("read", description="权限级别：read/write/admin")
    expires_at: Optional[datetime] = Field(None, description="过期时间（NULL表示永久）")


class PermissionResponse(BaseModel):
    id: int
    user_id: int
    resource_type: str
    resource_id: int
    permission_level: str
    granted_by: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]


class SetVisibilityRequest(BaseModel):
    visibility_level: str = Field(..., description="可见级别：private/major/college/school/public")


# ============================================================
# 权限检查辅助函数
# ============================================================

def check_subject_access(user_id: int, subject_id: int, db: Session) -> bool:
    """
    检查用户是否有访问科目的权限
    
    权限判断逻辑：
    1. 如果是所有者，直接有权限
    2. 根据可见级别判断：
       - public: 所有人可见
       - school: 同校用户可见
       - college: 同学院用户可见
       - major: 同专业用户可见
       - course: 同课程用户可见（暂时简化为同专业）
       - private: 只有所有者可见
    3. 检查是否有特殊授权
    """
    # 获取科目信息
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        return False
    
    # 1. 如果是所有者，直接有权限
    if subject.user_id == user_id:
        return True
    
    # 2. 如果是私有的，只有所有者可见
    if subject.visibility_level == VisibilityLevel.private:
        # 检查是否有特殊授权
        permission = db.query(DataAccessPermission).filter(
            and_(
                DataAccessPermission.user_id == user_id,
                DataAccessPermission.resource_type == ResourceType.subject,
                DataAccessPermission.resource_id == subject_id,
                or_(
                    DataAccessPermission.expires_at.is_(None),
                    DataAccessPermission.expires_at > datetime.now()
                )
            )
        ).first()
        return permission is not None
    
    # 3. 如果是公开的，所有人都有权限
    if subject.visibility_level == VisibilityLevel.public:
        return True
    
    # 4. 获取用户信息
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # 5. 根据可见级别判断
    if subject.visibility_level == VisibilityLevel.school:
        if user.school_id and user.school_id == subject.school_id:
            return True
    
    if subject.visibility_level == VisibilityLevel.college:
        if user.college_id and user.college_id == subject.college_id:
            return True
    
    if subject.visibility_level == VisibilityLevel.major:
        if user.major_id and user.major_id == subject.major_id:
            return True
    
    # 6. 检查是否有特殊授权
    permission = db.query(DataAccessPermission).filter(
        and_(
            DataAccessPermission.user_id == user_id,
            DataAccessPermission.resource_type == ResourceType.subject,
            DataAccessPermission.resource_id == subject_id,
            or_(
                DataAccessPermission.expires_at.is_(None),
                DataAccessPermission.expires_at > datetime.now()
            )
        )
    ).first()
    
    return permission is not None


def check_resource_owner(user_id: int, resource_type: str, resource_id: int, db: Session) -> bool:
    """检查用户是否是资源的所有者"""
    if resource_type == "subject":
        resource = db.query(Subject).filter(Subject.id == resource_id).first()
    elif resource_type == "question":
        resource = db.query(Question).filter(Question.id == resource_id).first()
    else:
        return False
    
    if not resource:
        return False
    
    return resource.user_id == user_id


# ============================================================
# 权限授予和撤销
# ============================================================

@router.post("/grant", response_model=PermissionResponse, summary="授予权限")
def grant_permission(
    request: GrantPermissionRequest,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    授予用户对资源的访问权限
    - 只有资源所有者可以授予权限
    - 支持设置过期时间
    """
    # 验证token
    payload = decode_token(token)
    current_user_id = payload.get("user_id")
    
    # 验证资源类型
    try:
        resource_type_enum = ResourceType(request.resource_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="资源类型无效，必须是 subject 或 question"
        )
    
    # 验证权限级别
    try:
        permission_level_enum = PermissionLevel(request.permission_level)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="权限级别无效，必须是 read、write 或 admin"
        )
    
    # 检查是否是资源所有者
    if not check_resource_owner(current_user_id, request.resource_type, request.resource_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有资源所有者可以授予权限"
        )
    
    # 检查目标用户是否存在
    target_user = db.query(User).filter(User.id == request.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="目标用户不存在"
        )
    
    # 检查是否已存在权限
    existing = db.query(DataAccessPermission).filter(
        and_(
            DataAccessPermission.user_id == request.user_id,
            DataAccessPermission.resource_type == resource_type_enum,
            DataAccessPermission.resource_id == request.resource_id
        )
    ).first()
    
    if existing:
        # 更新现有权限
        existing.permission_level = permission_level_enum
        existing.expires_at = request.expires_at
        existing.granted_by = current_user_id
        db.commit()
        db.refresh(existing)
        permission = existing
    else:
        # 创建新权限
        permission = DataAccessPermission(
            user_id=request.user_id,
            resource_type=resource_type_enum,
            resource_id=request.resource_id,
            permission_level=permission_level_enum,
            granted_by=current_user_id,
            expires_at=request.expires_at
        )
        db.add(permission)
        db.commit()
        db.refresh(permission)
    
    return {
        "id": permission.id,
        "user_id": permission.user_id,
        "resource_type": permission.resource_type.value,
        "resource_id": permission.resource_id,
        "permission_level": permission.permission_level.value,
        "granted_by": permission.granted_by,
        "created_at": permission.created_at,
        "expires_at": permission.expires_at
    }


@router.delete("/revoke", summary="撤销权限")
def revoke_permission(
    user_id: int,
    resource_type: str,
    resource_id: int,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    撤销用户对资源的访问权限
    - 只有资源所有者可以撤销权限
    """
    # 验证token
    payload = decode_token(token)
    current_user_id = payload.get("user_id")
    
    # 验证资源类型
    try:
        resource_type_enum = ResourceType(resource_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="资源类型无效"
        )
    
    # 检查是否是资源所有者
    if not check_resource_owner(current_user_id, resource_type, resource_id, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有资源所有者可以撤销权限"
        )
    
    # 查找权限记录
    permission = db.query(DataAccessPermission).filter(
        and_(
            DataAccessPermission.user_id == user_id,
            DataAccessPermission.resource_type == resource_type_enum,
            DataAccessPermission.resource_id == resource_id
        )
    ).first()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="权限记录不存在"
        )
    
    # 删除权限
    db.delete(permission)
    db.commit()
    
    return {"message": "权限已撤销"}


# ============================================================
# 可见级别设置
# ============================================================

@router.put("/subjects/{subject_id}/visibility", summary="设置科目可见级别")
def set_subject_visibility(
    subject_id: int,
    request: SetVisibilityRequest,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    设置科目的可见级别
    - 只有科目所有者可以设置
    """
    # 验证token
    payload = decode_token(token)
    current_user_id = payload.get("user_id")
    
    # 验证可见级别
    try:
        visibility_enum = VisibilityLevel(request.visibility_level)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="可见级别无效，必须是 private、major、college、school 或 public"
        )
    
    # 查找科目
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="科目不存在"
        )
    
    # 检查是否是所有者
    if subject.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有科目所有者可以设置可见级别"
        )
    
    # 更新可见级别
    old_visibility = subject.visibility_level
    subject.visibility_level = visibility_enum
    db.commit()
    
    return {
        "message": "可见级别已更新",
        "old_visibility": old_visibility.value,
        "new_visibility": visibility_enum.value
    }


# ============================================================
# 权限查询
# ============================================================

@router.get("/my-permissions", response_model=List[PermissionResponse], summary="查询我的权限")
def get_my_permissions(
    token: str,
    resource_type: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    查询当前用户被授予的所有权限
    - 可以按资源类型筛选
    """
    # 验证token
    payload = decode_token(token)
    user_id = payload.get("user_id")
    
    query = db.query(DataAccessPermission).filter(
        DataAccessPermission.user_id == user_id
    )
    
    if resource_type:
        try:
            rt = ResourceType(resource_type)
            query = query.filter(DataAccessPermission.resource_type == rt)
        except ValueError:
            pass
    
    permissions = query.order_by(DataAccessPermission.created_at.desc()).all()
    
    return [
        {
            "id": p.id,
            "user_id": p.user_id,
            "resource_type": p.resource_type.value,
            "resource_id": p.resource_id,
            "permission_level": p.permission_level.value,
            "granted_by": p.granted_by,
            "created_at": p.created_at,
            "expires_at": p.expires_at
        }
        for p in permissions
    ]


@router.get("/check-access/{subject_id}", summary="检查科目访问权限")
def check_access(
    subject_id: int,
    token: str,
    db: Session = Depends(get_default_db)
):
    """
    检查当前用户是否有访问指定科目的权限
    """
    # 验证token
    payload = decode_token(token)
    user_id = payload.get("user_id")
    
    has_access = check_subject_access(user_id, subject_id, db)
    
    return {
        "subject_id": subject_id,
        "has_access": has_access
    }
