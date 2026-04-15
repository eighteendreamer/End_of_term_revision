"""
Redis缓存客户端
提供统一的缓存操作接口
"""
import redis
import json
import logging
from typing import Any, Optional, Union
from functools import wraps
import hashlib

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端封装"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = True
    ):
        """
        初始化Redis客户端
        :param host: Redis主机地址
        :param port: Redis端口
        :param db: 数据库编号
        :param password: 密码
        :param decode_responses: 是否自动解码响应
        """
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.client.ping()
            logger.info(f"Redis连接成功: {host}:{port}/{db}")
        except redis.ConnectionError as e:
            logger.warning(f"Redis连接失败: {str(e)}，缓存功能将被禁用")
            self.client = None
        except Exception as e:
            logger.error(f"Redis初始化错误: {str(e)}")
            self.client = None
    
    def is_available(self) -> bool:
        """检查Redis是否可用"""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        :param key: 缓存键
        :return: 缓存值（自动JSON解析）
        """
        if not self.is_available():
            return None
        
        try:
            value = self.client.get(key)
            if value is None:
                return None
            
            # 尝试JSON解析
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis GET错误 [{key}]: {str(e)}")
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """
        设置缓存值
        :param key: 缓存键
        :param value: 缓存值（自动JSON序列化）
        :param expire: 过期时间（秒）
        :return: 是否成功
        """
        if not self.is_available():
            return False
        
        try:
            # 自动JSON序列化
            if not isinstance(value, (str, bytes)):
                value = json.dumps(value, ensure_ascii=False)
            
            if expire:
                return self.client.setex(key, expire, value)
            else:
                return self.client.set(key, value)
        except Exception as e:
            logger.error(f"Redis SET错误 [{key}]: {str(e)}")
            return False
    
    def delete(self, *keys: str) -> int:
        """
        删除缓存
        :param keys: 缓存键列表
        :return: 删除的数量
        """
        if not self.is_available() or not keys:
            return 0
        
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis DELETE错误: {str(e)}")
            return 0
    
    def exists(self, key: str) -> bool:
        """
        检查键是否存在
        :param key: 缓存键
        :return: 是否存在
        """
        if not self.is_available():
            return False
        
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis EXISTS错误 [{key}]: {str(e)}")
            return False
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        设置过期时间
        :param key: 缓存键
        :param seconds: 过期时间（秒）
        :return: 是否成功
        """
        if not self.is_available():
            return False
        
        try:
            return self.client.expire(key, seconds)
        except Exception as e:
            logger.error(f"Redis EXPIRE错误 [{key}]: {str(e)}")
            return False
    
    def ttl(self, key: str) -> int:
        """
        获取剩余过期时间
        :param key: 缓存键
        :return: 剩余秒数（-1表示永久，-2表示不存在）
        """
        if not self.is_available():
            return -2
        
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f"Redis TTL错误 [{key}]: {str(e)}")
            return -2
    
    def delete_pattern(self, pattern: str) -> int:
        """
        删除匹配模式的所有键
        :param pattern: 匹配模式（如 "user:*"）
        :return: 删除的数量
        """
        if not self.is_available():
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN错误 [{pattern}]: {str(e)}")
            return 0
    
    def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        递增计数器
        :param key: 缓存键
        :param amount: 递增量
        :return: 递增后的值
        """
        if not self.is_available():
            return None
        
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis INCR错误 [{key}]: {str(e)}")
            return None
    
    def decr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        递减计数器
        :param key: 缓存键
        :param amount: 递减量
        :return: 递减后的值
        """
        if not self.is_available():
            return None
        
        try:
            return self.client.decrby(key, amount)
        except Exception as e:
            logger.error(f"Redis DECR错误 [{key}]: {str(e)}")
            return None
    
    def hget(self, name: str, key: str) -> Optional[Any]:
        """
        获取哈希表字段值
        :param name: 哈希表名
        :param key: 字段名
        :return: 字段值
        """
        if not self.is_available():
            return None
        
        try:
            value = self.client.hget(name, key)
            if value is None:
                return None
            
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        except Exception as e:
            logger.error(f"Redis HGET错误 [{name}:{key}]: {str(e)}")
            return None
    
    def hset(self, name: str, key: str, value: Any) -> bool:
        """
        设置哈希表字段值
        :param name: 哈希表名
        :param key: 字段名
        :param value: 字段值
        :return: 是否成功
        """
        if not self.is_available():
            return False
        
        try:
            if not isinstance(value, (str, bytes)):
                value = json.dumps(value, ensure_ascii=False)
            
            return self.client.hset(name, key, value) >= 0
        except Exception as e:
            logger.error(f"Redis HSET错误 [{name}:{key}]: {str(e)}")
            return False
    
    def hgetall(self, name: str) -> dict:
        """
        获取哈希表所有字段
        :param name: 哈希表名
        :return: 字段字典
        """
        if not self.is_available():
            return {}
        
        try:
            data = self.client.hgetall(name)
            result = {}
            for key, value in data.items():
                try:
                    result[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = value
            return result
        except Exception as e:
            logger.error(f"Redis HGETALL错误 [{name}]: {str(e)}")
            return {}
    
    def hdel(self, name: str, *keys: str) -> int:
        """
        删除哈希表字段
        :param name: 哈希表名
        :param keys: 字段名列表
        :return: 删除的数量
        """
        if not self.is_available() or not keys:
            return 0
        
        try:
            return self.client.hdel(name, *keys)
        except Exception as e:
            logger.error(f"Redis HDEL错误 [{name}]: {str(e)}")
            return 0


# 全局Redis客户端实例
try:
    from config import config
    redis_client = RedisClient(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD
    )
except ImportError:
    # 如果config模块不存在，使用默认配置
    redis_client = RedisClient(
        host="localhost",
        port=6379,
        db=0,
        password=None
    )


def cache_key(*args, **kwargs) -> str:
    """
    生成缓存键
    :param args: 位置参数
    :param kwargs: 关键字参数
    :return: 缓存键
    """
    # 将参数转换为字符串
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_str = ":".join(key_parts)
    
    # 如果键太长，使用MD5哈希
    if len(key_str) > 200:
        key_hash = hashlib.md5(key_str.encode()).hexdigest()
        return f"{args[0] if args else 'cache'}:{key_hash}"
    
    return key_str


def cached(expire: int = 300, key_prefix: str = ""):
    """
    缓存装饰器
    :param expire: 过期时间（秒）
    :param key_prefix: 键前缀
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key_str = cache_key(
                key_prefix or func.__name__,
                *args,
                **kwargs
            )
            
            # 尝试从缓存获取
            cached_value = redis_client.get(cache_key_str)
            if cached_value is not None:
                logger.debug(f"缓存命中: {cache_key_str}")
                return cached_value
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 存入缓存
            redis_client.set(cache_key_str, result, expire)
            logger.debug(f"缓存写入: {cache_key_str}")
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    清除缓存
    :param pattern: 匹配模式
    """
    count = redis_client.delete_pattern(pattern)
    logger.info(f"清除缓存: {pattern} ({count}个键)")
    return count
