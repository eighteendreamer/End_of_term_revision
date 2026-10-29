# -*- coding: utf-8 -*-
"""
用户大模型配置的唯一读取入口。

此前 6 处 import 路由和 ai_question_generator 各自 `query(LLMModel).filter(
user_id==...).first()`，无排序、无默认概念：用户新增一条配置后导入仍可能命中
旧的那条，表现为"换了模型没生效"。这里收成一个函数，选谁、能不能用视觉，
都在一处判定。
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import LLMModel
from services.llm_client import LLMClient

DEFAULT_MAX_OUTPUT_TOKENS = 8192


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
        config = _pick_vision_capable(db, user_id) or config
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
