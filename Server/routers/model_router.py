"""
自定义模型路由

改动要点：
  * 读写一律按 user_id 收敛，之前 PUT/DELETE/GET 只按 model_id 匹配，
    任何登录用户改自己的 URL 就能读到或改掉别人的模型配置与密钥。
  * 响应不再回传明文 api_key，只回传掩码串。
  * base_url 放开内网与回环（自建 Ollama/vLLM 是常态用法），
    但链路本地与云元数据地址仍然硬拦。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.db import get_default_db
from database.models import LLMModel
from services.llm_config_service import (DEFAULT_MAX_OUTPUT_TOKENS,
                                         MAX_OUTPUT_TOKENS_BOUND,
                                         MIN_OUTPUT_TOKENS, list_models,
                                         mask_api_key, set_default)
from utils.security import validate_model_base_url

router = APIRouter(prefix="/api/models", tags=["模型配置"])

# 输出上限的取值范围与默认值来自 llm_config_service，这里不再重复写字面量
OUTPUT_LIMIT_RANGE = (MIN_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS_BOUND)


class ModelCreate(BaseModel):
    """创建模型配置请求"""
    user_id: int
    model_name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    supports_vision: bool = False
    supports_json_mode: bool = True
    max_output_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS,
                                   ge=OUTPUT_LIMIT_RANGE[0], le=OUTPUT_LIMIT_RANGE[1])
    is_default: bool = False


class ModelUpdate(BaseModel):
    """
    更新模型配置请求。

    api_key 省略即保持原值不变：读取接口已不再下发明文密钥，
    前端拿不到原值，不能要求用户每次重填。要换密钥就填新值，
    要废弃就整条删除重建。
    """
    user_id: int
    model_name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=255)
    api_key: Optional[str] = Field(default=None, min_length=1, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    supports_vision: bool = False
    supports_json_mode: bool = True
    max_output_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS,
                                   ge=OUTPUT_LIMIT_RANGE[0], le=OUTPUT_LIMIT_RANGE[1])


class ModelResponse(BaseModel):
    """模型配置响应（不含明文密钥）"""
    id: int
    user_id: int
    model_name: str
    display_name: str
    base_url: str
    api_key_masked: str
    is_default: bool
    supports_vision: bool
    supports_json_mode: bool
    max_output_tokens: int
    created_at: str


def _to_response(model: LLMModel) -> ModelResponse:
    return ModelResponse(
        id=model.id,
        user_id=model.user_id,
        model_name=model.model_name,
        display_name=model.display_name or model.model_name,
        base_url=model.base_url,
        api_key_masked=mask_api_key(model.api_key),
        is_default=bool(model.is_default),
        supports_vision=bool(model.supports_vision),
        supports_json_mode=bool(model.supports_json_mode),
        max_output_tokens=model.max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS,
        created_at=model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else "",
    )


def _owned(db: Session, model_id: int, user_id: int) -> LLMModel:
    model = (db.query(LLMModel)
             .filter(LLMModel.id == model_id, LLMModel.user_id == user_id)
             .first())
    if not model:
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return model


@router.post("/", response_model=ModelResponse)
def create_model_config(model: ModelCreate, db: Session = Depends(get_default_db)):
    """创建模型配置"""
    validate_model_base_url(model.base_url, "base_url")

    # 首条配置自动成为默认，省掉"建完还得点一下设为默认"
    becomes_default = model.is_default or not list_models(db, model.user_id)
    if becomes_default:
        (db.query(LLMModel).filter(LLMModel.user_id == model.user_id)
         .update({LLMModel.is_default: False}, synchronize_session=False))

    record = LLMModel(
        user_id=model.user_id,
        model_name=model.model_name,
        base_url=model.base_url,
        api_key=model.api_key,
        display_name=model.display_name,
        is_default=becomes_default,
        supports_vision=model.supports_vision,
        supports_json_mode=model.supports_json_mode,
        max_output_tokens=model.max_output_tokens,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.get("/defaults")
def get_model_defaults():
    """表单的默认值与取值范围由后端下发，前端不再抄一份字面量。"""
    return {"code": 200, "data": {
        "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        "min_output_tokens": MIN_OUTPUT_TOKENS,
        "max_output_tokens_bound": MAX_OUTPUT_TOKENS_BOUND,
    }}


@router.get("/", response_model=List[ModelResponse])
def get_model_configs(user_id: int = Query(...),
                      db: Session = Depends(get_default_db)):
    """获取用户的所有模型配置，默认项排前。"""
    return [_to_response(m) for m in list_models(db, user_id)]


@router.get("/{model_id}", response_model=ModelResponse)
def get_model_config(model_id: int, user_id: int = Query(...),
                     db: Session = Depends(get_default_db)):
    """获取单个模型配置。"""
    return _to_response(_owned(db, model_id, user_id))


@router.put("/{model_id}", response_model=ModelResponse)
def update_model_config(model_id: int,
                        model_update: ModelUpdate,
                        db: Session = Depends(get_default_db)):
    """更新模型配置。api_key 留空表示不改。"""
    validate_model_base_url(model_update.base_url, "base_url")
    record = _owned(db, model_id, model_update.user_id)

    record.model_name = model_update.model_name
    record.base_url = model_update.base_url
    record.display_name = model_update.display_name
    record.supports_vision = model_update.supports_vision
    record.supports_json_mode = model_update.supports_json_mode
    record.max_output_tokens = model_update.max_output_tokens
    if model_update.api_key:
        record.api_key = model_update.api_key

    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.post("/{model_id}/default", response_model=ModelResponse)
def make_model_default(model_id: int,
                       user_id: int = Query(...),
                       db: Session = Depends(get_default_db)):
    """把该配置设为用户的默认模型。"""
    record = _owned(db, model_id, user_id)
    set_default(db, user_id, model_id)
    db.refresh(record)
    return _to_response(record)


@router.delete("/{model_id}")
def delete_model_config(model_id: int,
                        user_id: int = Query(...),
                        db: Session = Depends(get_default_db)):
    """删除模型配置。"""
    record = _owned(db, model_id, user_id)
    was_default = bool(record.is_default)
    db.delete(record)
    db.commit()

    # 删掉的是默认项时把剩下最早的一条顶上来，避免导入功能突然没有模型可用
    if was_default:
        remaining = list_models(db, user_id)
        if remaining:
            set_default(db, user_id, remaining[0].id)
    return {"message": "模型配置删除成功"}
