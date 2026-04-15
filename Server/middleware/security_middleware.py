"""
安全防护中间件 - 防DDOS、恶意访问、恶意攻击
策略：已登录用户（携带有效token）不受限流约束，仅对匿名请求执行限流和封禁
"""
from fastapi import Request, HTTPException, status
from datetime import datetime, timedelta
from typing import Optional, Tuple
from utils.redis_client import redis_client
from database.models import IPBlacklist, RegionBlacklist
from sqlalchemy.orm import Session
from config import config
from utils.security import JWT_SECRET_KEY, JWT_ALGORITHM, decode_token_safe
import logging

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """安全防护中间件"""
    
    # 可信代理IP列表（从配置文件读取）
    TRUSTED_PROXIES = config.TRUSTED_PROXIES
    
    # ========== 匿名请求限流参数（仅对未登录用户生效） ==========
    # 单IP限流（适当放宽，避免正常登录流程被误伤）
    MAX_REQUESTS_PER_SECOND = 10        # 每秒最大请求数
    MAX_REQUESTS_PER_10_SECONDS = 40    # 10秒内最大请求数
    MAX_REQUESTS_PER_MINUTE = 80        # 每分钟最大请求数
    MAX_REQUESTS_PER_HOUR = 1000        # 每小时最大请求数
    
    # 全局限流（所有IP总和）
    GLOBAL_MAX_REQUESTS_PER_SECOND = 100    # 全局每秒最大请求数
    GLOBAL_MAX_REQUESTS_PER_MINUTE = 1000   # 全局每分钟最大请求数
    
    # 特定操作限流
    REGISTER_MAX_ATTEMPTS = 2     # 注册最大尝试次数（1分钟内）
    LOGIN_MAX_ATTEMPTS = 10       # 登录最大尝试次数（5分钟内），放宽以容纳正常用户
    
    # 封禁时长
    BLOCK_DURATION_SHORT = 3600   # 短期封禁时长（1小时）
    BLOCK_DURATION_LONG = 86400   # 长期封禁时长（24小时）
    
    @staticmethod
    def get_client_ip(request: Request) -> str:
        """
        获取客户端真实IP
        安全策略：
        1. 优先使用request.client.host（最可靠）
        2. 只有当请求来自可信代理时，才信任X-Forwarded-For
        3. 防止IP伪造攻击
        """
        # 1. 直接从client获取（最可靠的方式）
        if request.client:
            client_ip = request.client.host
            
            # 2. 如果是可信代理，则检查X-Forwarded-For
            if client_ip in SecurityMiddleware.TRUSTED_PROXIES:
                forwarded = request.headers.get("X-Forwarded-For")
                if forwarded:
                    # 取第一个IP（客户端真实IP）
                    real_ip = forwarded.split(",")[0].strip()
                    logger.debug(f"从可信代理获取真实IP: {real_ip} (代理: {client_ip})")
                    return real_ip
                
                # 尝试X-Real-IP
                real_ip = request.headers.get("X-Real-IP")
                if real_ip:
                    logger.debug(f"从可信代理获取真实IP: {real_ip} (代理: {client_ip})")
                    return real_ip
            
            # 3. 不是可信代理，直接返回client IP
            return client_ip
        
        return "unknown"
    
    @staticmethod
    def get_client_region(request: Request) -> str:
        """
        获取客户端区域
        可以从请求头获取，或使用GeoIP库解析
        """
        region = request.headers.get("X-Client-Region", "unknown")
        return region
    
    @staticmethod
    def check_ip_blacklist(ip: str, db: Session, block_type: str = "all") -> Tuple[bool, Optional[str]]:
        """
        检查IP是否在黑名单中
        :return: (是否被封禁, 封禁原因)
        """
        now = datetime.now()
        
        blacklist = db.query(IPBlacklist).filter(
            IPBlacklist.ip_address == ip,
            IPBlacklist.block_type.in_([block_type, "all"])
        ).first()
        
        if not blacklist:
            return False, None
        
        # 检查是否过期
        if blacklist.expires_at and blacklist.expires_at < now:
            db.delete(blacklist)
            db.commit()
            return False, None
        
        return True, blacklist.reason
    
    @staticmethod
    def check_region_blacklist(region: str, db: Session, block_type: str = "all") -> Tuple[bool, Optional[str]]:
        """
        检查区域是否在黑名单中
        :return: (是否被封禁, 封禁原因)
        """
        if region == "unknown":
            return False, None
        
        now = datetime.now()
        
        blacklist = db.query(RegionBlacklist).filter(
            RegionBlacklist.region == region,
            RegionBlacklist.block_type.in_([block_type, "all"])
        ).first()
        
        if not blacklist:
            return False, None
        
        # 检查是否过期
        if blacklist.expires_at and blacklist.expires_at < now:
            db.delete(blacklist)
            db.commit()
            return False, None
        
        return True, blacklist.reason
    
    @staticmethod
    def check_rate_limit(
        key: str,
        max_attempts: int,
        window_seconds: int,
        block_duration: int = None
    ) -> Tuple[bool, Optional[int]]:
        """
        检查限流
        :param key: Redis键
        :param max_attempts: 最大尝试次数
        :param window_seconds: 时间窗口（秒）
        :param block_duration: 封禁时长（秒），None表示不封禁
        :return: (是否允许, 剩余封禁时间)
        """
        # 检查是否已被封禁
        block_key = f"{key}:blocked"
        if redis_client.exists(block_key):
            ttl = redis_client.ttl(block_key)
            return False, ttl
        
        # 增加计数
        count = redis_client.incr(key)
        
        # Redis不可用时放行（降级策略：宁可放行也不误杀）
        if count is None:
            return True, None
        
        # 第一次访问，设置过期时间
        if count == 1:
            redis_client.expire(key, window_seconds)
        
        # 检查是否超过限制
        if count > max_attempts:
            if block_duration:
                # 封禁
                redis_client.set(block_key, "1", expire=block_duration)
                return False, block_duration
            else:
                # 不封禁，只是拒绝请求
                return False, None
        
        return True, None
    
    @staticmethod
    def add_to_blacklist(
        ip: str,
        db: Session,
        reason: str,
        block_type: str = "all",
        duration_seconds: int = None
    ):
        """
        添加IP到黑名单
        :param ip: IP地址
        :param db: 数据库会话
        :param reason: 封禁原因
        :param block_type: 封禁类型（字符串，会自动转为枚举）
        :param duration_seconds: 封禁时长（秒），None表示永久
        """
        try:
            from database.models import BlockType as BlockTypeEnum
            # 将字符串转为枚举
            bt = BlockTypeEnum(block_type)
        except (ValueError, KeyError):
            bt = block_type  # 回退：直接用字符串（某些SQLAlchemy版本支持）
        
        expires_at = None
        if duration_seconds:
            expires_at = datetime.now() + timedelta(seconds=duration_seconds)
        
        try:
            # 检查是否已存在
            existing = db.query(IPBlacklist).filter(
                IPBlacklist.ip_address == ip
            ).first()
            
            if existing:
                # 更新现有记录
                existing.reason = reason
                existing.block_type = bt
                existing.expires_at = expires_at
            else:
                # 创建新记录
                blacklist = IPBlacklist(
                    ip_address=ip,
                    reason=reason,
                    block_type=bt,
                    expires_at=expires_at
                )
                db.add(blacklist)
            
            db.commit()
            logger.warning(f"IP {ip} 已被加入黑名单: {reason}")
        except Exception as e:
            logger.error(f"写入黑名单失败: {type(e).__name__}: {e}")
            db.rollback()
    
    @staticmethod
    def is_authenticated(request: Request) -> bool:
        """
        检查请求是否携带有效的JWT token（已登录用户）
        仅做轻量级校验，不查数据库，不抛异常
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # 也检查 query 参数中的 token（部分接口通过 ?token= 传递）
            token = request.query_params.get("token")
            if not token:
                return False
        else:
            token = auth_header.split(" ", 1)[1]
        
        return decode_token_safe(token) is not None
    
    @staticmethod
    async def check_ddos_protection(request: Request, db: Session):
        """
        DDOS防护检查
        策略：已登录用户直接放行，仅对匿名请求执行限流
        """
        # ===== 已登录用户直接放行，不做任何限流 =====
        if SecurityMiddleware.is_authenticated(request):
            return
        
        ip = SecurityMiddleware.get_client_ip(request)
        
        # 检查IP黑名单（匿名请求才检查）
        is_blocked, reason = SecurityMiddleware.check_ip_blacklist(ip, db, "all")
        if is_blocked:
            logger.warning(f"被封禁的IP尝试访问: {ip}, 原因: {reason}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您的IP已被封禁: {reason}"
            )
        
        # 1. 全局限流检查（防止大量不同IP的分布式攻击）
        # 每秒全局限流
        global_second_key = "rate_limit:global:second"
        global_allowed, _ = SecurityMiddleware.check_rate_limit(
            global_second_key,
            max_attempts=SecurityMiddleware.GLOBAL_MAX_REQUESTS_PER_SECOND,
            window_seconds=1,
            block_duration=None  # 全局限流不封禁，只拒绝
        )
        
        if not global_allowed:
            logger.warning(f"全局每秒限流触发: IP={ip}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="系统繁忙，请稍后再试"
            )
        
        # 每分钟全局限流
        global_minute_key = "rate_limit:global:minute"
        global_allowed, _ = SecurityMiddleware.check_rate_limit(
            global_minute_key,
            max_attempts=SecurityMiddleware.GLOBAL_MAX_REQUESTS_PER_MINUTE,
            window_seconds=60,
            block_duration=None
        )
        
        if not global_allowed:
            logger.warning(f"全局每分钟限流触发: IP={ip}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="系统繁忙，请稍后再试"
            )
        
        # 2. 单IP限流检查（多层时间窗口，仅匿名请求）
        # 每秒限流
        second_key = f"rate_limit:ip:{ip}:second"
        allowed, block_time = SecurityMiddleware.check_rate_limit(
            second_key,
            max_attempts=SecurityMiddleware.MAX_REQUESTS_PER_SECOND,
            window_seconds=1,
            block_duration=SecurityMiddleware.BLOCK_DURATION_SHORT
        )
        
        if not allowed:
            SecurityMiddleware.add_to_blacklist(
                ip, db,
                reason="每秒请求频率过高（疑似DDOS攻击）",
                block_type="all",
                duration_seconds=block_time
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，已被封禁 {block_time // 60} 分钟"
            )
        
        # 10秒限流
        ten_second_key = f"rate_limit:ip:{ip}:10second"
        allowed, block_time = SecurityMiddleware.check_rate_limit(
            ten_second_key,
            max_attempts=SecurityMiddleware.MAX_REQUESTS_PER_10_SECONDS,
            window_seconds=10,
            block_duration=SecurityMiddleware.BLOCK_DURATION_SHORT
        )
        
        if not allowed:
            SecurityMiddleware.add_to_blacklist(
                ip, db,
                reason="10秒内请求频率过高（疑似DDOS攻击）",
                block_type="all",
                duration_seconds=block_time
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，已被封禁 {block_time // 60} 分钟"
            )
        
        # 每分钟限流
        minute_key = f"rate_limit:ip:{ip}:minute"
        allowed, block_time = SecurityMiddleware.check_rate_limit(
            minute_key,
            max_attempts=SecurityMiddleware.MAX_REQUESTS_PER_MINUTE,
            window_seconds=60,
            block_duration=SecurityMiddleware.BLOCK_DURATION_SHORT
        )
        
        if not allowed:
            SecurityMiddleware.add_to_blacklist(
                ip, db,
                reason="每分钟请求频率过高（疑似DDOS攻击）",
                block_type="all",
                duration_seconds=block_time
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，已被封禁 {block_time // 60} 分钟"
            )
        
        # 每小时限流
        hour_key = f"rate_limit:ip:{ip}:hour"
        allowed, _ = SecurityMiddleware.check_rate_limit(
            hour_key,
            max_attempts=SecurityMiddleware.MAX_REQUESTS_PER_HOUR,
            window_seconds=3600,
            block_duration=None
        )
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="您的请求次数已达到每小时上限，请稍后再试"
            )
    
    @staticmethod
    async def check_register_protection(request: Request, db: Session):
        """
        注册保护检查
        """
        ip = SecurityMiddleware.get_client_ip(request)
        region = SecurityMiddleware.get_client_region(request)
        
        # 检查IP黑名单
        is_blocked, reason = SecurityMiddleware.check_ip_blacklist(ip, db, "register")
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您的IP已被封禁，无法注册: {reason}"
            )
        
        # 检查区域黑名单
        is_blocked, reason = SecurityMiddleware.check_region_blacklist(region, db, "register")
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您所在区域已被封禁，无法注册: {reason}"
            )
        
        # IP注册限流（1分钟内最多2次）
        ip_key = f"rate_limit:register:ip:{ip}"
        allowed, block_time = SecurityMiddleware.check_rate_limit(
            ip_key,
            max_attempts=SecurityMiddleware.REGISTER_MAX_ATTEMPTS,
            window_seconds=60,
            block_duration=SecurityMiddleware.BLOCK_DURATION_SHORT
        )
        
        if not allowed:
            SecurityMiddleware.add_to_blacklist(
                ip, db,
                reason="注册频率过高",
                block_type="register",
                duration_seconds=block_time
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"注册过于频繁，已被封禁 {block_time // 60} 分钟"
            )
    
    @staticmethod
    async def check_login_protection(request: Request, db: Session):
        """
        登录保护检查
        """
        ip = SecurityMiddleware.get_client_ip(request)
        
        # 检查IP黑名单
        is_blocked, reason = SecurityMiddleware.check_ip_blacklist(ip, db, "login")
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您的IP已被封禁，无法登录: {reason}"
            )
        
        # IP登录限流（5分钟内最多5次）
        ip_key = f"rate_limit:login:ip:{ip}"
        allowed, block_time = SecurityMiddleware.check_rate_limit(
            ip_key,
            max_attempts=SecurityMiddleware.LOGIN_MAX_ATTEMPTS,
            window_seconds=300,
            block_duration=SecurityMiddleware.BLOCK_DURATION_SHORT
        )
        
        if not allowed:
            SecurityMiddleware.add_to_blacklist(
                ip, db,
                reason="登录尝试次数过多",
                block_type="login",
                duration_seconds=block_time
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"登录尝试过于频繁，已被封禁 {block_time // 60} 分钟"
            )
    
    @staticmethod
    def record_failed_login(ip: str, student_id: str):
        """
        记录失败的登录尝试
        - 同一 IP + 账号：5次失败后锁定该账号15分钟
        - 同一 IP 对不同账号：10次失败后封禁 IP 1小时
        """
        # 1. 单账号失败计数
        account_key = f"failed_login:{ip}:{student_id}"
        account_count = redis_client.incr(account_key)
        if account_count is None:
            account_count = 0
        if account_count == 1:
            redis_client.expire(account_key, 900)  # 15分钟窗口
        
        # 单账号失败超过5次，锁定该账号（对该IP）
        if account_count >= 5:
            lock_key = f"account_locked:{ip}:{student_id}"
            redis_client.set(lock_key, "1", expire=900)  # 锁定15分钟
            logger.warning(f"账号暂时锁定: IP={ip}, 学号={student_id}, 失败次数={account_count}")
        
        # 2. 同一 IP 对所有账号的总失败计数（检测撞库攻击）
        ip_total_key = f"failed_login_total:{ip}"
        ip_total = redis_client.incr(ip_total_key)
        if ip_total is None:
            ip_total = 0
        if ip_total == 1:
            redis_client.expire(ip_total_key, 3600)  # 1小时窗口
        
        logger.warning(f"登录失败: IP={ip}, 学号={student_id}, 账号失败={account_count}, IP总失败={ip_total}")
        
        # 同一 IP 总失败超过10次，疑似撞库攻击
        if ip_total >= 10:
            logger.error(f"疑似撞库攻击: IP={ip}, 总失败次数={ip_total}")
    
    @staticmethod
    def is_account_locked(ip: str, student_id: str) -> bool:
        """检查账号是否被锁定"""
        lock_key = f"account_locked:{ip}:{student_id}"
        return redis_client.exists(lock_key)
