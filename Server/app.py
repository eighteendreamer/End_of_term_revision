"""
FastAPI 主应用程序
End_of_term_revision - 神阁卷藏
"""
from fastapi import FastAPI, WebSocket, Depends, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routers import (
    subjects_router,
    questions_router,
    import_router,
    practice_router,
    error_router,
    model_router,
    auth_router,
    resource_router,
    shares_router,
    organization_router,  # 新增：组织架构管理
    permissions_router,   # 新增：权限管理
    leaderboard_router,   # 新增：排行榜
    exam_paper_router,    # 新增：试卷练习
    material_router,      # 新增：资料管理
    friendship_router,    # 新增：好友系统
    chat_router,          # 新增：聊天系统
    profile_router,       # 新增：个人信息管理
    exam_schedule_router  # 新增：考试倒计时
)
from routers import security_router  # 新增：安全管理
from websocket_server import handle_websocket, get_online_status
from middleware.rate_limiter import RateLimiter
from middleware.security_middleware import SecurityMiddleware
from utils.security import (
    SECURITY_HEADERS, decode_token_safe,
    check_sql_injection, check_xss,
    get_current_user_id
)
from database.db import get_default_db
from sqlalchemy.orm import Session
import os
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用（禁用自动文档）
app = FastAPI(
    title="End_of_term_revision API",
    description="神阁卷藏 - 支持多科目题库、AI 解析、错题集、自定义练习",
    version="1.0.0",
    docs_url=None,      # 禁用 /docs
    redoc_url=None,     # 禁用 /redoc
    openapi_url=None    # 禁用 /openapi.json
)

# 配置 CORS（收紧：仅允许前端域名）
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://endreversion.pantoria.cn").split(",") # ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3001")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# 注册路由
app.include_router(auth_router.router)
app.include_router(subjects_router.router)
app.include_router(questions_router.router)
app.include_router(import_router.router)
app.include_router(practice_router.router)
app.include_router(error_router.router)
app.include_router(model_router.router)
app.include_router(resource_router.router)
app.include_router(shares_router.router)
app.include_router(organization_router.router)  # 新增：组织架构管理路由
app.include_router(permissions_router.router)   # 新增：权限管理路由
app.include_router(leaderboard_router.router)   # 新增：排行榜路由
app.include_router(exam_paper_router.router)    # 新增：试卷练习路由
app.include_router(material_router.router)      # 新增：资料管理路由
app.include_router(friendship_router.router)    # 新增：好友系统路由
app.include_router(chat_router.router)          # 新增：聊天系统路由
app.include_router(profile_router.router)       # 新增：个人信息管理路由
app.include_router(security_router.router)      # 新增：安全管理路由
app.include_router(exam_schedule_router.router) # 新增：考试倒计时路由


# WebSocket路由（需要 token 鉴权）
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: str = Query(None)):
    """
    WebSocket连接端点（需要携带 token 参数鉴权）
    :param websocket: WebSocket连接
    :param user_id: 用户ID
    :param token: JWT token
    """
    # 鉴权：验证 token 并确认 user_id 匹配
    if not token:
        await websocket.close(code=4001, reason="缺少认证凭证")
        return
    payload = decode_token_safe(token)
    if not payload or payload.get("user_id") != user_id:
        await websocket.close(code=4003, reason="认证失败")
        return
    await handle_websocket(websocket, user_id)


# 在线状态查询（需要登录）
@app.get("/api/online-status/{user_id}")
def get_user_online_status(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取用户在线状态（需要登录）
    :param user_id: 目标用户ID
    :param current_user_id: 当前登录用户ID（从token中提取）
    """
    status = get_online_status(user_id)
    return {
        "code": 200,
        "message": "获取成功",
        "data": status
    }


# 注册安全中间件
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """安全防护中间件：限流 + 安全头 + 输入检测"""
    # 禁止访问文档接口
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        logger.warning(f"尝试访问被禁用的文档接口: {request.url.path}, IP: {SecurityMiddleware.get_client_ip(request)}")
        return JSONResponse(
            status_code=403,
            content={"detail": "API文档已被禁用"}
        )
    
    # 健康检查接口不需要安全检查
    if request.url.path == "/health" or request.url.path == "/":
        response = await call_next(request)
        # 即使是健康检查也加安全头
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        return response
    
    # ===== 输入安全检测：检查 URL 路径和查询参数是否包含注入攻击 =====
    ip = SecurityMiddleware.get_client_ip(request)
    attack_detected = False
    attack_reason = ""
    
    # 检查 URL 路径
    if check_sql_injection(request.url.path) or check_xss(request.url.path):
        attack_detected = True
        attack_reason = f"URL路径注入攻击: {request.url.path}"
    
    # 检查查询参数
    if not attack_detected:
        for key, value in request.query_params.items():
            if key == "token":  # token 参数跳过（JWT 本身包含特殊字符）
                continue
            if check_sql_injection(value) or check_xss(value):
                attack_detected = True
                attack_reason = f"查询参数注入攻击: {key}={value}"
                break
    
    # 如果检测到攻击，记录到数据库黑名单并拒绝
    if attack_detected:
        logger.warning(f"{attack_reason}, IP: {ip}")
        db_for_block = None
        try:
            from utils.redis_client import redis_client
            attack_count_key = f"attack_count:{ip}"
            attack_count = redis_client.incr(attack_count_key)
            if attack_count is None:
                attack_count = 1  # Redis不可用时默认计为1
            if attack_count == 1:
                redis_client.expire(attack_count_key, 3600)  # 1小时窗口
            
            logger.warning(f"攻击计数: IP={ip}, 次数={attack_count}")
            
            # 累计3次及以上，写入数据库黑名单封禁24小时
            if attack_count >= 3:
                db_for_block = next(get_default_db())
                SecurityMiddleware.add_to_blacklist(
                    ip, db_for_block,
                    reason=f"多次恶意攻击（{attack_reason}）",
                    block_type="all",
                    duration_seconds=86400  # 24小时
                )
                logger.error(f"恶意IP已加入黑名单: {ip}, 原因: {attack_reason}, 累计攻击次数: {attack_count}")
        except Exception as e:
            logger.error(f"记录恶意IP失败: {type(e).__name__}: {e}")
        finally:
            if db_for_block:
                db_for_block.close()
        
        return JSONResponse(
            status_code=400,
            content={"detail": "请求包含非法字符"}
        )
    
    db = None
    try:
        db = next(get_default_db())
        
        # 1. 全局DDOS防护（内部会判断：已登录用户直接放行，匿名请求才限流）
        await SecurityMiddleware.check_ddos_protection(request, db)
        
        # 2. 注册接口特殊保护（注册本身是匿名操作，保留限流）
        if request.url.path == "/api/auth/register":
            await SecurityMiddleware.check_register_protection(request, db)
        
        # 3. 登录接口特殊保护（登录本身是匿名操作，保留限流）
        if request.url.path == "/api/auth/login":
            await SecurityMiddleware.check_login_protection(request, db)
        
        response = await call_next(request)
        
        # ===== 为所有响应添加安全头 =====
        for key, value in SECURITY_HEADERS.items():
            response.headers[key] = value
        
        return response
        
    except HTTPException as e:
        logger.warning(f"安全拦截: {request.url.path}, IP: {SecurityMiddleware.get_client_ip(request)}, 原因: {e.detail}")
        return JSONResponse(
            status_code=e.status_code,
            content={"detail": e.detail}
        )
    except Exception as e:
        logger.error(f"安全中间件错误: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器内部错误"}
        )
    finally:
        if db:
            db.close()


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    print("\n" + "="*60)
    print("🎓 神阁卷藏 API 启动成功!")
    print("="*60)
    print(f"🔒 安全防护: 已启用 (DDOS/恶意访问/黑名单)")
    print(f"🔧 健康检查: http://localhost:8001/health")
    print(f"⚡ 版本: 1.0.0")
    print(f"⚠️  API文档: 已禁用 (/docs, /redoc)")
    print("="*60 + "\n")
    
    # 清理过期的黑名单记录
    try:
        from services.security_service import SecurityService
        db = next(get_default_db())
        result = SecurityService.clean_expired_blacklist(db)
        logger.info(f"启动时清理过期黑名单: IP={result['ip_count']}, 区域={result['region_count']}")
        db.close()
    except Exception as e:
        logger.error(f"清理过期黑名单失败: {str(e)}")


@app.get("/")
def root():
    """根路径（不使用数据库）"""
    return {
        "message": "Welcome to 神阁卷藏 API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
def health_check():
    """健康检查（不使用数据库，避免连接池耗尽）"""
    return {"status": "ok", "service": "End_of_term_revision"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
