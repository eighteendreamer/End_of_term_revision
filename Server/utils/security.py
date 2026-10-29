"""
集中式安全工具模块
- JWT 密钥统一管理
- 通用鉴权依赖
- 输入清洗工具
- 安全请求头
"""
import os
import re
import jwt
import html
import secrets
import ipaddress
import logging
from urllib.parse import urlparse
from fastapi import Request, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database.db import get_default_db
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================================
# JWT 配置（统一管理，从环境变量读取）
# ============================================================
_env_jwt_secret = os.getenv("JWT_SECRET_KEY")
if not _env_jwt_secret:
    # 未配置时回退为随机密钥：仅便于本地开发。
    # 生产环境必须显式设置固定的 JWT_SECRET_KEY，否则重启/多进程会导致所有令牌失效。
    logger.warning(
        "未设置环境变量 JWT_SECRET_KEY，已使用临时随机密钥（仅限开发）。"
        "生产环境请必须配置固定的 JWT_SECRET_KEY。"
    )
    _env_jwt_secret = secrets.token_hex(32)
JWT_SECRET_KEY = _env_jwt_secret
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 默认7天


def create_token(data: dict) -> str:
    """创建 JWT token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 JWT token，失败抛 401"""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.PyJWTError:
        # PyJWT 的异常基类（旧代码误写为 jwt.JWTError，在 PyJWT 中不存在，
        # 会导致非过期的非法 token 抛 AttributeError -> 500）
        raise HTTPException(status_code=401, detail="Token无效")


def decode_token_safe(token: str) -> Optional[dict]:
    """解码 JWT token，失败返回 None（不抛异常，用于中间件）"""
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


# ============================================================
# 通用鉴权依赖：从 token 中提取 user_id
# ============================================================
def _extract_token(request: Request) -> str:
    """从请求中提取 token（Header 或 Query 参数）"""
    # 优先从 Authorization header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    # 兼容 query 参数
    token = request.query_params.get("token")
    if token:
        return token
    raise HTTPException(status_code=401, detail="未提供认证凭证")


def get_current_user_id(request: Request) -> int:
    """
    FastAPI 依赖项：从 JWT token 中提取 user_id
    用法：current_user_id: int = Depends(get_current_user_id)
    """
    token = _extract_token(request)
    payload = decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token中缺少用户信息")
    return int(user_id)


# ============================================================
# 输入清洗工具：防 SQL 注入 & XSS
# ============================================================

# SQL 注入危险关键字模式
_SQL_INJECTION_PATTERN = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|EXEC|EXECUTE|"
    r"TRUNCATE|DECLARE|CAST|CONVERT|WAITFOR|DELAY|BENCHMARK|SLEEP|"
    r"LOAD_FILE|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b"
    r"|(--)|(;)|(\/\*)|(\*\/)|(xp_))",
    re.IGNORECASE
)

# XSS 危险标签模式
_XSS_PATTERN = re.compile(
    r"(<\s*script|<\s*iframe|<\s*object|<\s*embed|<\s*form|"
    r"javascript\s*:|on\w+\s*=|eval\s*\(|expression\s*\()",
    re.IGNORECASE
)


def sanitize_input(value: str) -> str:
    """
    清洗用户输入：
    1. 去除首尾空白
    2. HTML 实体转义（防 XSS）
    3. 检测 SQL 注入关键字
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    # HTML 转义
    value = html.escape(value, quote=True)
    return value


def check_sql_injection(value: str) -> bool:
    """检测字符串是否包含 SQL 注入特征，返回 True 表示危险"""
    if not isinstance(value, str):
        return False
    return bool(_SQL_INJECTION_PATTERN.search(value))


def check_xss(value: str) -> bool:
    """检测字符串是否包含 XSS 特征，返回 True 表示危险"""
    if not isinstance(value, str):
        return False
    return bool(_XSS_PATTERN.search(value))


def validate_safe_input(value: str, field_name: str = "输入") -> str:
    """
    验证并清洗输入，如果检测到注入攻击则抛出 400 错误
    """
    if not isinstance(value, str):
        return value
    if check_sql_injection(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}包含非法字符"
        )
    if check_xss(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}包含非法字符"
        )
    return sanitize_input(value)


# ============================================================
# SSRF 防护：校验外部 URL（用于用户自定义的 LLM base_url 等）
# ============================================================
_BLOCKED_URL_HOSTS = {"localhost", "metadata.google.internal"}

# 模型端点单独一份黑名单：localhost 是自建推理服务的常态地址，不能拦。
_MODEL_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal"}


def is_safe_external_url(url: str) -> bool:
    """
    粗粒度 SSRF 防护：拒绝指向本机/内网/云元数据地址的 URL。
    仅允许 http/https；若 host 为 IP 则拒绝私有/回环/链路本地/保留地址。
    为避免阻塞，不做 DNS 解析（域名仅按主机名黑名单拦截）。
    """
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _BLOCKED_URL_HOSTS:
        return False
    if host == "169.254.169.254":  # 云元数据服务
        return False
    try:
        ip = ipaddress.ip_address(host)
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    except ValueError:
        # host 为域名，非 IP：不做 DNS 解析
        pass
    return True


def validate_external_url(url: str, field_name: str = "URL") -> str:
    """校验外部 URL，不合法或指向内网则抛 400。"""
    if not is_safe_external_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 不合法或指向了不被允许的内网地址"
        )
    return url


def is_safe_model_base_url(url: str) -> bool:
    """
    模型端点地址校验。

    与通用外链不同：自建推理服务（Ollama、vLLM、内网 one-api 网关）本来就跑在
    localhost、回环或内网地址上，照搬 is_safe_external_url 的主机黑名单会让用户
    根本存不进配置——`http://localhost:11434/v1` 正是 Ollama 的默认地址。
    因此这里放开本机与内网，但链路本地、云元数据与保留地址仍然硬拦：
    那类地址一旦被服务端去请求，等于把云主机凭证暴露出去。
    """
    if not isinstance(url, str) or not url.strip():
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in _MODEL_BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True  # 域名：交给部署侧的网络策略约束，不在这里做 DNS 判定
    return not (ip.is_link_local or ip.is_reserved or ip.is_multicast
                or ip.is_unspecified)


def validate_model_base_url(url: str, field_name: str = "base_url") -> str:
    """模型地址不合法时抛 400，并说明被拦的具体原因。"""
    if not is_safe_model_base_url(url):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 必须是以 http/https 开头的模型服务地址，"
                   f"且不能指向链路本地或云元数据地址"
        )
    return url


# ============================================================
# 安全响应头
# ============================================================
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws: wss:; font-src 'self' data:;",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


# ============================================================
# 文件上传安全校验
# ============================================================
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/msword",  # doc
}
ALLOWED_UPLOAD_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOC_TYPES
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB

# 文件扩展名白名单
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}


def validate_file_upload(filename: str, content_type: str, file_size: int):
    """
    校验上传文件的安全性
    :raises HTTPException: 如果文件不合法
    """
    import os as _os
    # 检查文件扩展名
    ext = _os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型: {ext}，允许: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    # 检查 MIME 类型
    if content_type and content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {content_type}"
        )
    # 检查文件大小
    if file_size > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB）"
        )
    # 检查文件名安全性（防止路径穿越）
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="文件名包含非法字符"
        )
