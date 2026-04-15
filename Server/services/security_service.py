"""
安全服务 - 黑名单管理、安全日志、威胁检测
"""
from sqlalchemy.orm import Session
from database.models import IPBlacklist, RegionBlacklist
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from utils.redis_client import redis_client
import logging

logger = logging.getLogger(__name__)


class SecurityService:
    """安全服务类"""
    
    @staticmethod
    def get_ip_blacklist(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        block_type: Optional[str] = None
    ) -> Dict:
        """
        获取IP黑名单列表
        """
        query = db.query(IPBlacklist)
        
        if block_type:
            query = query.filter(IPBlacklist.block_type == block_type)
        
        # 总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        items = query.order_by(IPBlacklist.created_at.desc()).offset(offset).limit(page_size).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "ip_address": item.ip_address,
                    "reason": item.reason,
                    "block_type": item.block_type.value,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                    "created_at": item.created_at.isoformat(),
                    "is_permanent": item.expires_at is None
                }
                for item in items
            ]
        }
    
    @staticmethod
    def add_ip_to_blacklist(
        db: Session,
        ip_address: str,
        reason: str,
        block_type: str = "all",
        duration_hours: Optional[int] = None
    ) -> IPBlacklist:
        """
        手动添加IP到黑名单
        """
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        # 检查是否已存在
        existing = db.query(IPBlacklist).filter(
            IPBlacklist.ip_address == ip_address
        ).first()
        
        if existing:
            # 更新现有记录
            existing.reason = reason
            existing.block_type = block_type
            existing.expires_at = expires_at
            db.commit()
            logger.info(f"更新IP黑名单: {ip_address}")
            return existing
        else:
            # 创建新记录
            blacklist = IPBlacklist(
                ip_address=ip_address,
                reason=reason,
                block_type=block_type,
                expires_at=expires_at
            )
            db.add(blacklist)
            db.commit()
            logger.info(f"添加IP到黑名单: {ip_address}, 原因: {reason}")
            return blacklist
    
    @staticmethod
    def remove_ip_from_blacklist(db: Session, ip_address: str) -> bool:
        """
        从黑名单中移除IP
        """
        blacklist = db.query(IPBlacklist).filter(
            IPBlacklist.ip_address == ip_address
        ).first()
        
        if blacklist:
            db.delete(blacklist)
            db.commit()
            logger.info(f"从黑名单移除IP: {ip_address}")
            return True
        
        return False
    
    @staticmethod
    def get_region_blacklist(
        db: Session,
        page: int = 1,
        page_size: int = 20
    ) -> Dict:
        """
        获取区域黑名单列表
        """
        query = db.query(RegionBlacklist)
        
        # 总数
        total = query.count()
        
        # 分页
        offset = (page - 1) * page_size
        items = query.order_by(RegionBlacklist.created_at.desc()).offset(offset).limit(page_size).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "region": item.region,
                    "reason": item.reason,
                    "block_type": item.block_type.value,
                    "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                    "created_at": item.created_at.isoformat(),
                    "is_permanent": item.expires_at is None
                }
                for item in items
            ]
        }
    
    @staticmethod
    def add_region_to_blacklist(
        db: Session,
        region: str,
        reason: str,
        block_type: str = "all",
        duration_hours: Optional[int] = None
    ) -> RegionBlacklist:
        """
        添加区域到黑名单
        """
        expires_at = None
        if duration_hours:
            expires_at = datetime.now() + timedelta(hours=duration_hours)
        
        # 检查是否已存在
        existing = db.query(RegionBlacklist).filter(
            RegionBlacklist.region == region
        ).first()
        
        if existing:
            # 更新现有记录
            existing.reason = reason
            existing.block_type = block_type
            existing.expires_at = expires_at
            db.commit()
            logger.info(f"更新区域黑名单: {region}")
            return existing
        else:
            # 创建新记录
            blacklist = RegionBlacklist(
                region=region,
                reason=reason,
                block_type=block_type,
                expires_at=expires_at
            )
            db.add(blacklist)
            db.commit()
            logger.info(f"添加区域到黑名单: {region}, 原因: {reason}")
            return blacklist
    
    @staticmethod
    def remove_region_from_blacklist(db: Session, region: str) -> bool:
        """
        从黑名单中移除区域
        """
        blacklist = db.query(RegionBlacklist).filter(
            RegionBlacklist.region == region
        ).first()
        
        if blacklist:
            db.delete(blacklist)
            db.commit()
            logger.info(f"从黑名单移除区域: {region}")
            return True
        
        return False
    
    @staticmethod
    def clean_expired_blacklist(db: Session) -> Dict[str, int]:
        """
        清理过期的黑名单记录
        """
        now = datetime.now()
        
        # 清理过期的IP黑名单
        ip_count = db.query(IPBlacklist).filter(
            IPBlacklist.expires_at.isnot(None),
            IPBlacklist.expires_at < now
        ).delete()
        
        # 清理过期的区域黑名单
        region_count = db.query(RegionBlacklist).filter(
            RegionBlacklist.expires_at.isnot(None),
            RegionBlacklist.expires_at < now
        ).delete()
        
        db.commit()
        
        logger.info(f"清理过期黑名单: IP={ip_count}, 区域={region_count}")
        
        return {
            "ip_count": ip_count,
            "region_count": region_count
        }
    
    @staticmethod
    def get_security_stats(db: Session) -> Dict:
        """
        获取安全统计信息
        """
        # IP黑名单统计
        total_ip_blocked = db.query(IPBlacklist).count()
        permanent_ip_blocked = db.query(IPBlacklist).filter(
            IPBlacklist.expires_at.is_(None)
        ).count()
        
        # 区域黑名单统计
        total_region_blocked = db.query(RegionBlacklist).count()
        permanent_region_blocked = db.query(RegionBlacklist).filter(
            RegionBlacklist.expires_at.is_(None)
        ).count()
        
        # Redis中的限流统计
        rate_limit_keys = redis_client.keys("rate_limit:*:blocked")
        active_blocks = len(rate_limit_keys) if rate_limit_keys else 0
        
        return {
            "ip_blacklist": {
                "total": total_ip_blocked,
                "permanent": permanent_ip_blocked,
                "temporary": total_ip_blocked - permanent_ip_blocked
            },
            "region_blacklist": {
                "total": total_region_blocked,
                "permanent": permanent_region_blocked,
                "temporary": total_region_blocked - permanent_region_blocked
            },
            "active_rate_limits": active_blocks
        }
    
    @staticmethod
    def get_suspicious_activities(db: Session, hours: int = 24) -> List[Dict]:
        """
        获取可疑活动记录
        """
        # 从Redis获取失败登录记录
        failed_login_keys = redis_client.keys("failed_login:*")
        suspicious = []
        
        if failed_login_keys:
            for key in failed_login_keys[:100]:  # 限制返回数量
                key_str = key.decode() if isinstance(key, bytes) else key
                parts = key_str.split(":")
                if len(parts) >= 3:
                    ip = parts[1]
                    student_id = parts[2]
                    count = redis_client.get(key_str)
                    ttl = redis_client.ttl(key_str)
                    
                    suspicious.append({
                        "type": "failed_login",
                        "ip": ip,
                        "student_id": student_id,
                        "attempts": int(count) if count else 0,
                        "ttl_seconds": ttl
                    })
        
        return suspicious
