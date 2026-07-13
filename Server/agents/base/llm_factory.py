# -*- coding: utf-8 -*-
"""
LLM 工厂 — 从用户数据库配置创建 LangChain ChatOpenAI 实例
"""
from langchain_openai import ChatOpenAI
from typing import Optional
from sqlalchemy.orm import Session

from database.models import LLMModel


def create_llm(base_url: str, api_key: str, model_name: str,
              temperature: float = 0.3) -> ChatOpenAI:
    """
    创建 LangChain ChatOpenAI 实例
    :param base_url: API 基础地址
    :param api_key: API 密钥
    :param model_name: 模型名称
    :param temperature: 温度参数
    :return: ChatOpenAI 实例
    """
    return ChatOpenAI(
        model=model_name,
        openai_api_base=base_url,
        openai_api_key=api_key,
        temperature=temperature,
    )


def create_llm_from_config(llm_config: LLMModel,
                            temperature: float = 0.3) -> ChatOpenAI:
    """
    从 LLMModel ORM 对象创建 LLM 实例
    :param llm_config: 用户的 LLM 配置
    :param temperature: 温度参数
    :return: ChatOpenAI 实例
    """
    return create_llm(
        base_url=llm_config.base_url,
        api_key=llm_config.api_key,
        model_name=llm_config.model_name,
        temperature=temperature,
    )


def get_llm_from_db(db: Session, user_id: int,
                   temperature: float = 0.3) -> ChatOpenAI:
    """
    从数据库获取用户 LLM 配置并创建实例
    :param db: 数据库会话
    :param user_id: 用户 ID
    :param temperature: 温度参数
    :return: ChatOpenAI 实例
    :raises ValueError: 如果用户未配置 LLM
    """
    llm_config = db.query(LLMModel).filter(
        LLMModel.user_id == user_id
    ).first()
    if not llm_config:
        raise ValueError("请先配置 AI 模型")
    return create_llm_from_config(llm_config, temperature)
