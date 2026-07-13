# -*- coding: utf-8 -*-
"""
统一题目 JSON 输出解析器
使用 Pydantic 模型定义输出 schema，配合 LangChain 的 JsonOutputParser
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_core.output_parsers import JsonOutputParser


class QuestionResource(BaseModel):
    """题目附属资源（公式代码、图表代码等）"""
    type: str = Field(description="资源类型: latex | code | diagram_desc | other")
    content: str = Field(description="资源内容（LaTeX 公式或 Python 代码）")
    description: Optional[str] = Field(default=None, description="资源描述")


class QuestionModel(BaseModel):
    """单道题目的数据模型"""
    type: str = Field(description="题型: single/multiple/judge/fill/major")
    question: str = Field(description="题干内容")
    options: List[str] = Field(default_factory=list, description="选项列表")
    answer: str = Field(description="正确答案")
    analysis: str = Field(description="答案解析")
    resources: Optional[List[QuestionResource]] = Field(
        default=None,
        description="公式/图表资源列表"
    )


class QuestionSetModel(BaseModel):
    """题目集合"""
    subject: str = Field(description="科目名称")
    questions: List[QuestionModel] = Field(description="题目列表")


def get_question_parser() -> JsonOutputParser:
    """获取统一题目输出解析器"""
    return JsonOutputParser(pydantic_object=QuestionSetModel)


def get_format_instructions() -> str:
    """获取格式说明文本"""
    return get_question_parser().get_format_instructions()
