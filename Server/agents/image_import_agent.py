# -*- coding: utf-8 -*-
"""
图片导入 Agent — 双路并行 + AI 仲裁
Vision 模型直接解析 + Unlimited-OCR 提取文本 → AI 对比校验 → 最终合并
"""
import base64
from typing import TypedDict, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from utils.schema_validator import parse_and_validate, normalize_question_data
from agents.base.ocr_client import UnlimitedOCRClient
from agents.base.output_parser import get_format_instructions
from agents.base.prompts import (
    IMAGE_VISION_PROMPT,
    IMAGE_VERIFY_PROMPT,
)


# ============================================================
# 状态定义
# ============================================================

class ImageImportState(TypedDict):
    """图片导入 Agent 的工作流状态"""
    image_path: str             # 图片路径
    subject: str                # 科目
    vision_result: str          # Vision 模型解析结果 JSON
    ocr_text: str              # OCR 提取的 Markdown 文本
    final_questions: dict       # 最终题目 JSON
    error: str                  # 错误信息


# ============================================================
# Agent 类
# ============================================================

class ImageImportAgent:
    """
    图片导入 Agent — 双路并行 + AI 仲裁

    通道 A: LLM Vision 直接解析图片 → Question JSON（主路径）
    通道 B: Unlimited-OCR 提取文本 → Markdown（校验路径）
    仲裁: AI 对比两个结果，取并集，补全遗漏，修正公式
    """

    def __init__(self, llm: ChatOpenAI,
                 ocr_client: Optional[UnlimitedOCRClient] = None):
        """
        :param llm: LangChain ChatOpenAI 实例（需支持 Vision）
        :param ocr_client: 百度 Unlimited-OCR 客户端（可选）
        """
        self.llm = llm
        self.ocr_client = ocr_client

        # 构建仲裁链
        self.verify_chain = IMAGE_VERIFY_PROMPT | self.llm | StrOutputParser()

    def invoke(self, image_path: str, subject: str) -> Dict[str, Any]:
        """
        执行图片导入

        :param image_path: 图片路径
        :param subject: 科目名称
        :return: {"subject": str, "questions": [...]}
        """
        # 构建工作流图
        graph = self._build_graph()
        initial_state: ImageImportState = {
            "image_path": image_path,
            "subject": subject,
            "vision_result": "",
            "ocr_text": "",
            "final_questions": {},
            "error": "",
        }
        result = graph.invoke(initial_state)

        if result.get("error"):
            print(f"[ImageAgent] 工作流错误: {result['error']}")

        questions = result.get("final_questions", {})
        if not questions.get("questions"):
            # 降级：尝试只用 Vision 结果
            print("[ImageAgent] 仲裁流程未解析出题目，尝试用 Vision 原始结果")
            questions = self._fallback_vision(image_path, subject)

        return questions

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流"""

        def vision_parse(state: ImageImportState) -> dict:
            """节点 A: LLM Vision 直接解析图片为题目 JSON"""
            try:
                # 读取图片并编码
                with open(state["image_path"], "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()

                ext = state["image_path"].lower().split(".")[-1]
                mime = f"image/{ext if ext in ['png', 'jpeg', 'jpg', 'webp', 'gif'] else 'jpeg'}"
                image_url = f"data:{mime};base64,{image_data}"

                # 使用 ChatPromptTemplate 格式化消息
                formatted = IMAGE_VISION_PROMPT.format_messages(
                    image_url=image_url,
                    subject=state["subject"],
                    format_instructions=get_format_instructions(),
                )

                # 调用 Vision 模型
                response = self.llm.invoke(formatted)
                result_text = response.content if hasattr(response, 'content') else str(response)

                print(f"[ImageAgent] Vision 解析完成, 长度: {len(result_text)}")
                return {"vision_result": result_text}
            except Exception as e:
                print(f"[ImageAgent] Vision 解析失败: {e}")
                return {"vision_result": "", "error": str(e)}

        def ocr_extract(state: ImageImportState) -> dict:
            """节点 B: Unlimited-OCR 提取文本"""
            if not self.ocr_client:
                print("[ImageAgent] OCR 客户端未配置，跳过 OCR 通道")
                return {"ocr_text": ""}

            try:
                result = self.ocr_client.parse_image(
                    state["image_path"], max_wait=60
                )
                markdown = result.get("markdown", "")
                print(f"[ImageAgent] OCR 提取完成, 文本长度: {len(markdown)}")
                return {"ocr_text": markdown}
            except Exception as e:
                print(f"[ImageAgent] OCR 失败，跳过: {e}")
                return {"ocr_text": ""}

        def verify_and_merge(state: ImageImportState) -> dict:
            """节点: AI 仲裁 — 对比 Vision 和 OCR 结果"""
            # 如果 OCR 文本为空，直接使用 Vision 结果
            if not state.get("ocr_text"):
                print("[ImageAgent] 无 OCR 文本，直接使用 Vision 结果")
                try:
                    parsed = parse_and_validate(state["vision_result"])
                    questions = parsed.get("questions") or []
                    for q in questions:
                        normalize_question_data(q)
                    return {"final_questions": parsed}
                except Exception as e:
                    return {
                        "final_questions": {
                            "subject": state["subject"],
                            "questions": [],
                        },
                        "error": str(e),
                    }

            # 双路仲裁
            try:
                result_str = self.verify_chain.invoke({
                    "vision_result": state["vision_result"][:6000],
                    "ocr_text": state["ocr_text"][:6000],
                    "subject": state["subject"],
                    "format_instructions": get_format_instructions(),
                })

                parsed = parse_and_validate(result_str)
                questions = parsed.get("questions") or []
                for q in questions:
                    normalize_question_data(q)

                print(f"[ImageAgent] 仲裁合并完成, {len(questions)} 道题目")
                return {"final_questions": parsed}
            except Exception as e:
                print(f"[ImageAgent] 仲裁失败: {e}")
                # 降级：尝试用 Vision 原始结果
                try:
                    parsed = parse_and_validate(state["vision_result"])
                    return {"final_questions": parsed}
                except Exception:
                    return {
                        "final_questions": {
                            "subject": state["subject"],
                            "questions": [],
                        },
                        "error": str(e),
                    }

        # --- 构建工作流图 ---

        graph = StateGraph(ImageImportState)
        graph.add_node("vision_parse", vision_parse)
        graph.add_node("ocr_extract", ocr_extract)
        graph.add_node("verify_merge", verify_and_merge)

        # 从 START 并行 fan-out 到两个节点
        graph.add_edge(START, "vision_parse")
        graph.add_edge(START, "ocr_extract")

        # 两者完成后汇合到 verify_merge
        graph.add_edge("vision_parse", "verify_merge")
        graph.add_edge("ocr_extract", "verify_merge")
        graph.add_edge("verify_merge", END)

        return graph.compile()

    def _fallback_vision(self, image_path: str, subject: str) -> dict:
        """降级方案：只用 Vision 模型解析"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()

            ext = image_path.lower().split(".")[-1]
            mime = f"image/{ext if ext in ['png', 'jpeg', 'jpg', 'webp'] else 'jpeg'}"
            image_url = f"data:{mime};base64,{image_data}"

            formatted = IMAGE_VISION_PROMPT.format_messages(
                image_url=image_url,
                subject=subject,
                format_instructions=get_format_instructions(),
            )

            response = self.llm.invoke(formatted)
            result_text = response.content if hasattr(response, 'content') else str(response)

            parsed = parse_and_validate(result_text)
            questions = parsed.get("questions") or []
            for q in questions:
                normalize_question_data(q)

            return parsed
        except Exception as e:
            print(f"[ImageAgent] 降级 Vision 也失败: {e}")
            return {"subject": subject, "questions": []}
