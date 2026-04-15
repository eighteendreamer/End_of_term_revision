"""
应用配置文件
"""
import os
from typing import Optional


class Config:
    """应用配置类"""
    
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)
    
    # 缓存过期时间（秒）
    CACHE_EXPIRE_SHORT: int = 300  # 5分钟
    CACHE_EXPIRE_MEDIUM: int = 600  # 10分钟
    CACHE_EXPIRE_LONG: int = 1800  # 30分钟
    
    # 数据库配置
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:root@localhost:3306/end_of_term_revision"
    )
    
    # MinIO配置
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "endreversion")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    
    # 安全配置 - 可信代理IP列表
    # 在生产环境中，应该配置实际的Nginx/Apache等反向代理服务器IP
    TRUSTED_PROXIES: list = [
        "127.0.0.1",  # 本地
        "::1",        # IPv6本地
        # 添加你的反向代理服务器IP，例如：
        # "10.0.0.1",
        # "192.168.1.1",
    ]


# 全局配置实例
config = Config()
