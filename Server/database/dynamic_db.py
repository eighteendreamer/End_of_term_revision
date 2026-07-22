"""
动态数据库连接模块
根据用户配置的数据库信息创建连接
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Dict
from collections import OrderedDict
import threading

# 存储每个用户的数据库引擎（带上限的 LRU 缓存，防止引擎/连接池无限增长）
_MAX_CACHED_ENGINES = 50
_user_engines: "OrderedDict[int, any]" = OrderedDict()
_lock = threading.Lock()


def get_user_db_url(db_config: dict) -> str:
    """
    根据数据库配置生成连接 URL
    :param db_config: 数据库配置字典
    :return: 数据库连接 URL
    """
    return (
        f"mysql+pymysql://{db_config['db_user']}:{db_config['db_password']}"
        f"@{db_config['db_host']}:{db_config['db_port']}"
        f"/{db_config['db_name']}?charset=utf8mb4"
    )


def get_dynamic_engine(user_id: int, db_config: dict):
    """
    获取用户的动态数据库引擎
    :param user_id: 用户 ID
    :param db_config: 数据库配置
    :return: SQLAlchemy Engine
    """
    with _lock:
        # 如果已存在该用户的引擎，先关闭旧的
        if user_id in _user_engines:
            _user_engines.pop(user_id).dispose()
        
        # 创建新引擎（合理的连接池大小）
        db_url = get_user_db_url(db_config)
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=5,            # 每个用户的连接池较小
            max_overflow=10,        # 溢出连接数
            pool_timeout=30,        # 连接超时时间
            echo=False
        )
        _user_engines[user_id] = engine
        # 超过上限时淘汰最久未使用的引擎并释放其连接池
        while len(_user_engines) > _MAX_CACHED_ENGINES:
            _old_uid, _old_engine = _user_engines.popitem(last=False)
            _old_engine.dispose()
        return engine


def get_user_session(user_id: int, db_config: dict):
    """
    获取用户的数据库会话
    :param user_id: 用户 ID
    :param db_config: 数据库配置
    :return: SQLAlchemy Session
    """
    engine = get_dynamic_engine(user_id, db_config)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def close_user_engine(user_id: int):
    """
    关闭用户的数据库引擎
    :param user_id: 用户 ID
    """
    with _lock:
        if user_id in _user_engines:
            _user_engines[user_id].dispose()
            del _user_engines[user_id]
