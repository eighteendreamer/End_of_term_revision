"""
防恶意注册中间件 - IP和区域限流
"""
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
from typing import Optional
from utils.redis_client import redis_client
from database.models import IPBlacklist, RegionBlacklist
from sqlalchemy.orm import Session


class RateLimiter:
    """限流器"""
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """获取客户端真实IP"""
        # 优先从X-Forwarded-For获取（考虑代理情况）
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        # 从X-Real-IP获取
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 直接从client获取
        if request.client:
            return request.client.host
        
        return "unknown"
    
    @staticmethod
    def get_client_region(request: Request) -> str:
        """
        获取客户端区域
        这里简化处理，实际应该使用IP地理位置库（如GeoIP2）
        """
        # 从请求头获取区域信息（需要前端或网关传递）
        region = request.headers.get("X-Client-Region", "unknown")
        return region
    
    @staticmethod
    def check_ip_blacklist(ip: str, db: Session, block_type: str = "register") -> bool:
        """
        检查IP是否在黑名单中
        :param ip: IP地址
        :param db: 数据库会话
        :param block_type: 检查类型（register/login/all）
        :return: True表示被封禁
        """
        now = datetime.now()
        
        # 查询黑名单
        blacklist = db.query(IPBlacklist).filter(
            IPBlacklist.ip_address == ip,
            IPBlacklist.block_type.in_([block_type, "all"])
        ).first()
        
        if not blacklist:
            return False
        
        # 检查是否过期
        if blacklist.expires_at and blacklist.expires_at < now:
            # 已过期，删除记录
            db.delete(blacklist)
            db.commit()
            return False
        
        return True
    
    @staticmethod
    def check_region_blacklist(region: str, db: Session, block_type: str = "register") -> bool:
        """
        检查区域是否在黑名单中
        :param region: 区域标识
        :param db: 数据库会话
        :param block_type: 检查类型（register/login/all）
        :return: True表示被封禁
        """
        if region == "unknown":
            return False
        
        now = datetime.now()
        
        # 查询黑名单
        blacklist = db.query(RegionBlacklist).filter(
            RegionBlacklist.region == region,
            RegionBlacklist.block_type.in_([block_type, "all"])
        ).first()
        
        if not blacklist:
            return False
        
        # 检查是否过期
        if blacklist.expires_at and blacklist.expires_at < now:
            # 已过期，删除记录
            db.delete(blacklist)
            db.commit()
            return False
        
        return True
    
    @staticmethod
    def check_rate_limit(
        key: str,
        max_attempts: int = 2,
        window_seconds: int = 60,
        block_duration: int = 3600
    ) -> tuple[bool, Optional[int]]:
        """
        检查限流
        :param key: Redis键
        :param max_attempts: 最大尝试次数
        :param window_seconds: 时间窗口（秒）
        :param block_duration: 封禁时长（秒）
        :return: (是否允许, 剩余封禁时间)
        """
        # 检查是否已被封禁
        block_key = f"{key}:blocked"
        if redis_client.exists(block_key):
            ttl = redis_client.ttl(block_key)
            return False, ttl
        
        # 增加计数
        count = redis_client.incr(key)
        
        # 第一次访问，设置过期时间
        if count == 1:
            redis_client.expire(key, window_seconds)
        
        # 检查是否超过限制
        if count > max_attempts:
            # 封禁IP/区域
            redis_client.set(block_key, "1", expire=block_duration)
            return False, block_duration
        
        return True, None
    
    @staticmethod
    async def check_register_rate_limit(request: Request, db: Session):
        """
        检查注册限流
        同IP一分钟超2次注册封锁1小时
        同区域一分钟超2次封锁1小时
        """
        ip = RateLimiter.get_client_ip(request)
        region = RateLimiter.get_client_region(request)
        
        # 检查IP黑名单
        if RateLimiter.check_ip_blacklist(ip, db, "register"):
            raise HTTPException(
                status_code=403,
                detail="您的IP已被封禁，无法注册"
            )
        
        # 检查区域黑名单
        if RateLimiter.check_region_blacklist(region, db, "register"):
            raise HTTPException(
                status_code=403,
                detail="您所在区域已被封禁，无法注册"
            )
        
        # 检查IP限流
        ip_key = f"rate_limit:register:ip:{ip}"
        ip_allowed, ip_block_time = RateLimiter.check_rate_limit(
            ip_key, max_attempts=2, window_seconds=60, block_duration=3600
        )
        
        if not ip_allowed:
            # 添加到IP黑名单（临时）
            expires_at = datetime.now() + timedelta(seconds=ip_block_time)
            blacklist = IPBlacklist(
                ip_address=ip,
                reason="注册频率过高",
                block_type="register",
                expires_at=expires_at
            )
            db.add(blacklist)
            db.commit()
            
            raise HTTPException(
                status_code=429,
                detail=f"注册过于频繁，请{ip_block_time // 60}分钟后再试"
            )
        
        # 检查区域限流
        if region != "unknown":
            region_key = f"rate_limit:register:region:{region}"
            region_allowed, region_block_time = RateLimiter.check_rate_limit(
                region_key, max_attempts=2, window_seconds=60, block_duration=3600
            )
            
            if not region_allowed:
                # 添加到区域黑名单（临时）
                expires_at = datetime.now() + timedelta(seconds=region_block_time)
                blacklist = RegionBlacklist(
                    region=region,
                    reason="注册频率过高",
                    block_type="register",
                    expires_at=expires_at
                )
                db.add(blacklist)
                db.commit()
                
                raise HTTPException(
                    status_code=429,
                    detail=f"该区域注册过于频繁，请{region_block_time // 60}分钟后再试"
                )
