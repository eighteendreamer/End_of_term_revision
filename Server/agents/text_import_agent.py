# -*- coding: utf-8 -*-
"""
文本导入 Agent — 基于现有逻辑重构为 LangChain LCEL Chain
智能拆分题目与答案，复用 QuestionPreprocessor 和现有提示词
"""
import json
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from services.question_preprocessor import QuestionPreprocessor
from services.ai_parser import split_text_for_questions
from utils.schema_validator import parse_and_validate, normalize_question_data
from agents.base.prompts import (
    TEXT_PARSE_PROMPT,
    STRUCTURED_PARSE_PROMPT,
)
from agents.base.output_parser import get_question_parser, get_format_instructions


class TextImportAgent:
    """
    文本导入 Agent

    工作流程:
    1. 正则预处理 (QuestionPreprocessor) → 提取题号、题型、选项，计算置信度
    2. 根据置信度选择策略:
       - 置信度 >= 0.7 → 结构化 AI 处理 (预处理结果 + AI 补充答案解析)
       - 置信度 < 0.7  → 全文本 AI 处理 (AI 直接从原文解析)
    3. 如果首次解析为空 → 分段并发解析
    4. Schema 校验 + 标准化
    """

    def __init__(self, llm: ChatOpenAI):
        """
        :param llm: LangChain ChatOpenAI 实例
        """
        self.llm = llm
        self.preprocessor = QuestionPreprocessor()
        self.parser = get_question_parser()
        self._build_chains()

    def _build_chains(self):
        """构建 LCEL 链"""
        # 全文本解析链
        self.full_text_chain = TEXT_PARSE_PROMPT | self.llm | StrOutputParser()

        # 结构化解析链
        self.structured_chain = (
            STRUCTURED_PARSE_PROMPT | self.llm | StrOutputParser()
        )

    def invoke(self, text: str, subject: str) -> Dict[str, Any]:
        """
        执行文本导入

        :param text: 用户粘贴的文本
        :param subject: 科目名称
        :return: {"subject": str, "questions": list}
        """
        if not text.strip():
            raise ValueError("文本内容为空")

        text_length = len(text)
        print(f"[TextAgent] 收到文本: 科目={subject}, "
              f"长度={text_length} 字符")

        # 1. 预处理
        structured_questions = self.preprocessor.extract_questions_structure(text)
        avg_confidence = self.preprocessor.calculate_average_confidence(
            structured_questions
        )
        print(f"[TextAgent] 预处理: {len(structured_questions)} 道题目, "
              f"平均置信度: {avg_confidence:.2f}")

        # 2. 根据置信度选择策略
        if len(structured_questions) > 0 and avg_confidence >= 0.7:
            print("[TextAgent] 使用结构化 AI 处理")
            json_result = self._parse_structured(structured_questions, subject)
        else:
            print("[TextAgent] 使用全文本 AI 处理")
            json_result = self._parse_full_text(text, subject)

        # 3. 验证
        try:
            parsed_data = parse_and_validate(json_result)
        except (ValueError, TypeError) as e:
            print(f"[TextAgent] JSON 解析失败: {e}")
            parsed_data = {"subject": subject, "questions": []}

        questions = parsed_data.get("questions") or []
        print(f"[TextAgent] 首次解析: {len(questions)} 道题目")

        # 4. 空结果降级：分段处理
        if not questions:
            print("[TextAgent] 首次解析为空, 启动分段解析")
            questions = self._segmented_parse(text, subject)

        # 5. 标准化
        for q in questions:
            normalize_question_data(q)

        print(f"[TextAgent] 最终输出: {len(questions)} 道题目")
        return {"subject": subject, "questions": questions}

    def _parse_full_text(self, text: str, subject: str) -> str:
        """全文本 AI 解析"""
        try:
            result = self.full_text_chain.invoke({
                "text": text,
                "subject": subject,
                "format_instructions": get_format_instructions(),
            })
            return result
        except Exception as e:
            print(f"[TextAgent] 全文本解析失败: {e}")
            return '{"subject": "' + subject + '", "questions": []}'

    def _parse_structured(self, structured_questions: List[Dict[str, Any]],
                         subject: str) -> str:
        """结构化 AI 解析"""
        try:
            result = self.structured_chain.invoke({
                "structured_data": json.dumps(
                    structured_questions, ensure_ascii=False, indent=2
                ),
                "subject": subject,
            })
            return result
        except Exception as e:
            print(f"[TextAgent] 结构化解析失败, 降级为全文本: {e}")
            return '{"subject": "' + subject + '", "questions": []}'

    def _segmented_parse(self, text: str, subject: str) -> List[Dict[str, Any]]:
        """分段并发解析（复用现有 split_text_for_questions）"""
        segments = split_text_for_questions(text)
        print(f"[TextAgent] 分段数量: {len(segments)}")

        if not segments:
            return []

        def parse_segment(idx: int, segment: str) -> tuple:
            try:
                print(f"[TextAgent] 处理第 {idx + 1} 段, "
                      f"长度: {len(segment)} 字符")
                result = self.full_text_chain.invoke({
                    "text": segment,
                    "subject": subject,
                    "format_instructions": get_format_instructions(),
                })
                segment_data = parse_and_validate(result)
                segment_questions = segment_data.get("questions") or []
                for q in segment_questions:
                    normalize_question_data(q)
                print(f"[TextAgent] 第 {idx + 1} 段解析出 "
                      f"{len(segment_questions)} 道题目")
                return (idx, segment_questions)
            except Exception as e:
                print(f"[TextAgent] 第 {idx + 1} 段解析失败: {e}")
                return (idx, [])

        merged: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {
                executor.submit(parse_segment, i, seg): i
                for i, seg in enumerate(segments)
            }
            results = []
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"[TextAgent] 分段 {idx} 异常: {e}")
                    results.append((idx, []))

        # 按索引排序并合并
        results.sort(key=lambda x: x[0])
        for _, qs in results:
            merged.extend(qs)

        print(f"[TextAgent] 分段汇总: {len(merged)} 道题目")
        return merged


def import_text(text: str, subject: str, llm: ChatOpenAI) -> Dict[str, Any]:
    """
    文本导入入口函数

    :param text: 用户粘贴的文本
    :param subject: 科目名称
    :param llm: LangChain ChatOpenAI 实例
    :return: {"subject": str, "questions": list}
    """
    agent = TextImportAgent(llm)
    return agent.invoke(text, subject)
