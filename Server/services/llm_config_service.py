# -*- coding: utf-8 -*-
"""
用户大模型配置的唯一读取入口。

此前 6 处 import 路由和 ai_question_generator 各自 `query(LLMModel).filter(
user_id==...).first()`，无排序、无默认概念：用户新增一条配置后导入仍可能命中
旧的那条，表现为"换了模型没生效"。这里收成一个函数，选谁、能不能用视觉，
都在一处判定。
"""
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from database.models import LLMModel
from services.llm_client import LLMClient

# 输出预算的取值范围与兜底默认值，全仓只在这里定义一次；
# 建表/迁移 SQL 的 DEFAULT 与之对齐由 test_llm_schema_contract 钉住
DEFAULT_MAX_OUTPUT_TOKENS = 8192
MIN_OUTPUT_TOKENS = 256
MAX_OUTPUT_TOKENS_BOUND = 200000
PROBE_TIMEOUT = 10.0
# 各家 OpenAI 兼容端字段名不统一，按优先级逐个试；都没有就判定"端点没说"
OUTPUT_LIMIT_FIELDS = ("max_output_tokens", "max_completion_tokens")


def _http_get(url: str, headers: Dict[str, str]):
    return requests.get(url, headers=headers, timeout=PROBE_TIMEOUT)


def _limit_from(payload: Any) -> Optional[int]:
    if not isinstance(payload, dict) or payload.get("error"):
        return None
    limits = payload.get("limits")
    for key in OUTPUT_LIMIT_FIELDS:
        value = payload.get(key)
        if isinstance(value, int) and value > 0:
            return min(max(value, MIN_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS_BOUND)
    if isinstance(limits, dict) and isinstance(limits.get("output"), int):
        value = limits["output"]
        if value > 0:
            return min(max(value, MIN_OUTPUT_TOKENS), MAX_OUTPUT_TOKENS_BOUND)
    return None


def probe_max_output_tokens(base_url: str, api_key: str,
                            model_name: str) -> Optional[int]:
    """
    问端点要"这个模型一次最多能吐多少 token"。

    拿不到就返回 None，由调用方沿用手填值并如实标注来源。不猜：猜大了请求被
    400 拒掉，猜小了整批被静默截断，两种都比"不知道"更糟。
    注意有网关会用 HTTP 200 返回 error 体，所以只看 JSON 内容不看状态码不够。
    """
    headers = {"Authorization": "Bearer " + (api_key or "")}
    root = (base_url or "").rstrip("/")
    single = "%s/models/%s" % (root, model_name)
    try:
        response = _http_get(single, headers)
        if response.status_code == 200:
            direct = _limit_from(response.json())
            if direct:
                return direct
        listing = _http_get("%s/models" % root, headers)
        if listing.status_code != 200:
            return None
        body = listing.json()
        items = body.get("data") if isinstance(body, dict) else None
        for item in items or []:
            if isinstance(item, dict) and item.get("id") == model_name:
                return _limit_from(item)
    except Exception:
        return None
    return None


class NoModelConfigured(Exception):
    """用户还没有任何模型配置。"""


class VisionRequired(Exception):
    """任务需要视觉能力，但用户没有可用的视觉模型。"""


def list_models(db: Session, user_id: int) -> List[LLMModel]:
    """按"默认优先、其次创建顺序"稳定排序。"""
    return (db.query(LLMModel)
            .filter(LLMModel.user_id == user_id)
            .order_by(LLMModel.is_default.desc(), LLMModel.id.asc())
            .all())


def get_user_llm(db: Session, user_id: int, model_id: Optional[int] = None,
                 need_vision: bool = False) -> LLMModel:
    """
    取本次任务要用的模型配置。

    :param model_id: 前端显式选择的配置；必须属于该用户，不能越权取别人的
    :param need_vision: 图片/文档导入为 True，会自动改挑一个支持视觉的配置
    """
    if model_id is not None:
        config = (db.query(LLMModel)
                  .filter(LLMModel.id == model_id, LLMModel.user_id == user_id)
                  .first())
        if config is None:
            raise NoModelConfigured("指定的模型配置不存在或不属于当前用户")
    else:
        configs = list_models(db, user_id)
        if not configs:
            raise NoModelConfigured("请先在「AI 模型配置」页面添加模型")
        config = configs[0]

    if need_vision and not config.supports_vision:
        vision = _pick_vision_capable(db, user_id)
        if vision is None:
            raise VisionRequired(
                "图片导入和文档导入需要支持图片输入的模型：请到「AI 模型配置」"
                "勾选「支持图片输入」，或添加一个视觉模型后重试。"
                "把图片发给纯文本模型只会得到编造出来的题目。")
        config = vision
    return config


def build_client(config: LLMModel, temperature: float = 0.2) -> LLMClient:
    """按配置构造客户端；输出预算与 JSON 模式能力都来自这条配置本身。"""
    return LLMClient(
        base_url=config.base_url,
        api_key=config.api_key,
        model_name=config.model_name,
        temperature=temperature,
        supports_json_mode=bool(config.supports_json_mode),
        max_output_tokens=config.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
    )


def set_default(db: Session, user_id: int, model_id: int) -> LLMModel:
    """把指定配置设为该用户唯一默认项。"""
    target = (db.query(LLMModel)
              .filter(LLMModel.id == model_id, LLMModel.user_id == user_id)
              .first())
    if target is None:
        raise NoModelConfigured("指定的模型配置不存在或不属于当前用户")

    (db.query(LLMModel)
     .filter(LLMModel.user_id == user_id, LLMModel.id != model_id)
     .update({LLMModel.is_default: False}, synchronize_session=False))
    target.is_default = True
    db.commit()
    db.refresh(target)
    return target


def mask_api_key(api_key: str) -> str:
    """对外只回显足够辨认的片段，不把密钥下发到浏览器。"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:3]}{'*' * 6}{api_key[-4:]}"


def _pick_vision_capable(db: Session, user_id: int) -> Optional[LLMModel]:
    return (db.query(LLMModel)
            .filter(LLMModel.user_id == user_id, LLMModel.supports_vision.is_(True))
            .order_by(LLMModel.is_default.desc(), LLMModel.id.asc())
            .first())
