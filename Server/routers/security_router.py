"""
安全管理路由 - 黑名单管理、安全监控
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from database.db import get_default_db
from services.security_service import SecurityService
from middleware.security_middleware import SecurityMiddleware
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["安全管理"])


# ============================================================
# Pydantic 模型
# ============================================================

class AddIPBlacklistRequest(BaseModel):
    """添加IP黑名单请求"""
    ip_address: str
    reason: str
    block_type: str = "all"  # register/login/all
    duration_hours: Optional[int] = None  # None表示永久


class AddRegionBlacklistRequest(BaseModel):
    """添加区域黑名单请求"""
    region: str
    reason: str
    block_type: str = "all"
    duration_hours: Optional[int] = None


# ============================================================
# IP黑名单管理
# ============================================================

@router.get("/ip-blacklist")
def get_ip_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    block_type: Optional[str] = Query(None),
    db: Session = Depends(get_default_db)
):
    """
    获取IP黑名单列表
    """
    try:
        result = SecurityService.get_ip_blacklist(db, page, page_size, block_type)
        return {
            "code": 200,
            "message": "获取成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"获取IP黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ip-blacklist")
def add_ip_to_blacklist(
    request: AddIPBlacklistRequest,
    db: Session = Depends(get_default_db)
):
    """
    添加IP到黑名单
    """
    try:
        # 验证block_type
        if request.block_type not in ["register", "login", "all"]:
            raise HTTPException(status_code=400, detail="无效的封禁类型")
        
        blacklist = SecurityService.add_ip_to_blacklist(
            db,
            request.ip_address,
            request.reason,
            request.block_type,
            request.duration_hours
        )
        
        return {
            "code": 200,
            "message": "添加成功",
            "data": {
                "id": blacklist.id,
                "ip_address": blacklist.ip_address,
                "reason": blacklist.reason,
                "block_type": blacklist.block_type.value,
                "expires_at": blacklist.expires_at.isoformat() if blacklist.expires_at else None
            }
        }
    except Exception as e:
        logger.error(f"添加IP黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/ip-blacklist/{ip_address}")
def remove_ip_from_blacklist(
    ip_address: str,
    db: Session = Depends(get_default_db)
):
    """
    从黑名单中移除IP
    """
    try:
        success = SecurityService.remove_ip_from_blacklist(db, ip_address)
        
        if success:
            return {
                "code": 200,
                "message": "移除成功"
            }
        else:
            raise HTTPException(status_code=404, detail="IP不在黑名单中")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除IP黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 区域黑名单管理
# ============================================================

@router.get("/region-blacklist")
def get_region_blacklist(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_default_db)
):
    """
    获取区域黑名单列表
    """
    try:
        result = SecurityService.get_region_blacklist(db, page, page_size)
        return {
            "code": 200,
            "message": "获取成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"获取区域黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/region-blacklist")
def add_region_to_blacklist(
    request: AddRegionBlacklistRequest,
    db: Session = Depends(get_default_db)
):
    """
    添加区域到黑名单
    """
    try:
        # 验证block_type
        if request.block_type not in ["register", "login", "all"]:
            raise HTTPException(status_code=400, detail="无效的封禁类型")
        
        blacklist = SecurityService.add_region_to_blacklist(
            db,
            request.region,
            request.reason,
            request.block_type,
            request.duration_hours
        )
        
        return {
            "code": 200,
            "message": "添加成功",
            "data": {
                "id": blacklist.id,
                "region": blacklist.region,
                "reason": blacklist.reason,
                "block_type": blacklist.block_type.value,
                "expires_at": blacklist.expires_at.isoformat() if blacklist.expires_at else None
            }
        }
    except Exception as e:
        logger.error(f"添加区域黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/region-blacklist/{region}")
def remove_region_from_blacklist(
    region: str,
    db: Session = Depends(get_default_db)
):
    """
    从黑名单中移除区域
    """
    try:
        success = SecurityService.remove_region_from_blacklist(db, region)
        
        if success:
            return {
                "code": 200,
                "message": "移除成功"
            }
        else:
            raise HTTPException(status_code=404, detail="区域不在黑名单中")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"移除区域黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 安全监控
# ============================================================

@router.get("/stats")
def get_security_stats(db: Session = Depends(get_default_db)):
    """
    获取安全统计信息
    """
    try:
        stats = SecurityService.get_security_stats(db)
        return {
            "code": 200,
            "message": "获取成功",
            "data": stats
        }
    except Exception as e:
        logger.error(f"获取安全统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suspicious-activities")
def get_suspicious_activities(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_default_db)
):
    """
    获取可疑活动记录
    """
    try:
        activities = SecurityService.get_suspicious_activities(db, hours)
        return {
            "code": 200,
            "message": "获取成功",
            "data": activities
        }
    except Exception as e:
        logger.error(f"获取可疑活动失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clean-expired")
def clean_expired_blacklist(db: Session = Depends(get_default_db)):
    """
    清理过期的黑名单记录
    """
    try:
        result = SecurityService.clean_expired_blacklist(db)
        return {
            "code": 200,
            "message": "清理成功",
            "data": result
        }
    except Exception as e:
        logger.error(f"清理过期黑名单失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-ip/{ip_address}")
def check_ip_status(
    ip_address: str,
    db: Session = Depends(get_default_db)
):
    """
    检查IP状态
    """
    try:
        is_blocked, reason = SecurityMiddleware.check_ip_blacklist(ip_address, db, "all")
        
        return {
            "code": 200,
            "message": "查询成功",
            "data": {
                "ip_address": ip_address,
                "is_blocked": is_blocked,
                "reason": reason
            }
        }
    except Exception as e:
        logger.error(f"检查IP状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
