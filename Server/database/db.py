"""
默认数据库连接配置
用于初始化和管理员数据库
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import os

# 默认数据库配置（优先从环境变量读取）
DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:qwer4321@localhost:3306/end_of_term_revision?charset=utf8mb4"
)

# 创建默认引擎（合理的连接池大小，避免超出MySQL max_connections）
default_engine = create_engine(
    DEFAULT_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,           # 连接池核心大小（MySQL默认max_connections=151）
    max_overflow=20,        # 溢出连接数（高峰期最多10+20=30连接）
    pool_timeout=30,        # 获取连接超时时间
    echo=False
)

# 创建会话工厂
DefaultSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=default_engine)

# 创建基类
Base = declarative_base()


def get_default_db():
    """获取默认数据库会话"""
    db = DefaultSessionLocal()
    try:
        yield db
    finally:
        db.close()
