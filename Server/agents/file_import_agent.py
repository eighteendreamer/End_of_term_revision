# -*- coding: utf-8 -*-
"""
文件导入 Agent — 基于 LangGraph 工作流
Unlimited-OCR 初步识别 → AI 校验 → 公式/图表复现 → 题目结构化
"""
from typing import TypedDict, Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

from services.file_reader import FileReader
from utils.schema_validator import parse_and_validate, normalize_question_data
from agents.base.ocr_client import UnlimitedOCRClient
from agents.base.output_parser import get_format_instructions
from agents.base.prompts import (
    FILE_OCR_VERIFY_PROMPT,
    FORMULA_REPRODUCE_PROMPT,
    FILE_STRUCTURE_PROMPT,
)


# ============================================================
# 状态定义
# ============================================================

class FileImportState(TypedDict):
    """文件导入 Agent 的工作流状态"""
    file_path: str               # 文件路径
    subject: str                 # 科目
    ocr_markdown: str            # OCR 输出的 Markdown
    ocr_result: dict             # OCR 输出的 JSON
    reference_text: str          # 参考文本（FileReader 提取）
    verify_report: str           # 校验报告 JSON
    reproduce_result: str        # 公式/图表复现结果 JSON
    final_questions: dict        # 最终题目 JSON
    error: str                   # 错误信息


# ============================================================
# Agent 类
# ============================================================

class FileImportAgent:
    """
    文件导入 Agent

    工作流程:
    1. 文件预处理 → 判断类型
    2. 并行: Unlimited-OCR 解析 + FileReader 参考文本提取
    3. AI 校验: 对比 OCR 结果和参考文本
    4. 公式/图表复现: 生成 LaTeX 和 matplotlib 代码
    5. 题目结构化: 综合所有信息输出 Question JSON
    """

    def __init__(self, llm: ChatOpenAI,
                 ocr_client: Optional[UnlimitedOCRClient] = None):
        """
        :param llm: LangChain ChatOpenAI 实例
        :param ocr_client: 百度 Unlimited-OCR 客户端（可选，为 None 时降级）
        """
        self.llm = llm
        self.llm_low_temp = llm  # 复用同一实例
        self.ocr_client = ocr_client

        # 构建校验链
        self.verify_chain = FILE_OCR_VERIFY_PROMPT | self.llm | StrOutputParser()
        # 构建公式/图表复现链
        self.reproduce_chain = FORMULA_REPRODUCE_PROMPT | self.llm | StrOutputParser()
        # 构建题目结构化链
        self.structure_chain = FILE_STRUCTURE_PROMPT | self.llm | StrOutputParser()

    def invoke(self, file_path: str, subject: str) -> Dict[str, Any]:
        """
        执行文件导入

        :param file_path: 文件路径
        :param subject: 科目名称
        :return: {"subject": str, "questions": [...]}
        """
        # 构建工作流图
        graph = self._build_graph()
        initial_state: FileImportState = {
            "file_path": file_path,
            "subject": subject,
            "ocr_markdown": "",
            "ocr_result": {},
            "reference_text": "",
            "verify_report": "",
            "reproduce_result": "",
            "final_questions": {},
            "error": "",
        }
        result = graph.invoke(initial_state)

        if result.get("error"):
            print(f"[FileAgent] 工作流错误: {result['error']}")

        questions = result.get("final_questions", {})
        if not questions.get("questions"):
            # 最终降级：尝试直接用 FileReader 文本解析
            print("[FileAgent] Agent 流程未解析出题目，降级为直接文本解析")
            questions = self._fallback_parse(file_path, subject)

        return questions

    def _build_graph(self) -> StateGraph:
        """构建 LangGraph 工作流"""

        # --- 节点定义（闭包捕获 self.llm 和 self.ocr_client）---

        def run_ocr(state: FileImportState) -> dict:
            """节点: Unlimited-OCR 解析"""
            if not self.ocr_client:
                # 降级：用 FileReader 提取文本作为 OCR 结果
                print("[FileAgent] OCR 客户端未配置，降级为 FileReader 文本提取")
                try:
                    text = FileReader.read_file(state["file_path"])
                    return {"ocr_markdown": text, "ocr_result": {}}
                except Exception as e:
                    return {"ocr_markdown": "", "ocr_result": {}, "error": str(e)}

            try:
                result = self.ocr_client.parse_document(
                    state["file_path"], max_wait=180
                )
                return {
                    "ocr_markdown": result["markdown"],
                    "ocr_result": result.get("parse_result", {}),
                }
            except Exception as e:
                print(f"[FileAgent] OCR 失败，降级为 FileReader: {e}")
                try:
                    text = FileReader.read_file(state["file_path"])
                    return {"ocr_markdown": text, "ocr_result": {}}
                except Exception as e2:
                    return {"ocr_markdown": "", "ocr_result": {}, "error": str(e2)}

        def extract_reference(state: FileImportState) -> dict:
            """节点: 参考文本提取（复用 FileReader）"""
            try:
                text = FileReader.read_file(state["file_path"])
                return {"reference_text": text}
            except Exception as e:
                print(f"[FileAgent] 参考文本提取失败: {e}")
                return {"reference_text": ""}

        def ai_verify(state: FileImportState) -> dict:
            """节点: AI 校验 — 对比 OCR 结果和参考文本"""
            try:
                report = self.verify_chain.invoke({
                    "ocr_markdown": state["ocr_markdown"][:8000],
                    "reference_text": state["reference_text"][:8000],
                })
                print(f"[FileAgent] 校验完成, 报告长度: {len(report)}")
                return {"verify_report": report}
            except Exception as e:
                print(f"[FileAgent] 校验失败: {e}")
                return {"verify_report": "{}"}

        def reproduce_formulas(state: FileImportState) -> dict:
            """节点: 公式/图表复现"""
            try:
                result = self.reproduce_chain.invoke({
                    "ocr_text": state["ocr_markdown"][:6000],
                    "verify_issues": state["verify_report"][:3000],
                })
                print(f"[FileAgent] 公式/图表复现完成")
                return {"reproduce_result": result}
            except Exception as e:
                print(f"[FileAgent] 公式/图表复现失败: {e}")
                return {"reproduce_result": "{}"}

        def structure_questions(state: FileImportState) -> dict:
            """节点: 题目结构化 — 综合 OCR + 校验 + 复现结果"""
            try:
                json_str = self.structure_chain.invoke({
                    "subject": state["subject"],
                    "ocr_markdown": state["ocr_markdown"][:8000],
                    "verify_report": state["verify_report"][:3000],
                    "reproduce_result": state["reproduce_result"][:3000],
                    "format_instructions": get_format_instructions(),
                })

                # 校验和标准化
                parsed_data = parse_and_validate(json_str)
                questions = parsed_data.get("questions") or []
                for q in questions:
                    normalize_question_data(q)

                print(f"[FileAgent] 结构化完成, {len(questions)} 道题目")
                return {"final_questions": parsed_data}
            except Exception as e:
                print(f"[FileAgent] 结构化失败: {e}")
                return {
                    "final_questions": {
                        "subject": state["subject"],
                        "questions": [],
                    },
                    "error": str(e),
                }

        # --- 构建工作流图 ---

        graph = StateGraph(FileImportState)
        graph.add_node("ocr", run_ocr)
        graph.add_node("reference", extract_reference)
        graph.add_node("verify", ai_verify)
        graph.add_node("reproduce", reproduce_formulas)
        graph.add_node("structure", structure_questions)

        # 从 START 并行 fan-out 到 ocr 和 reference
        graph.add_edge(START, "ocr")
        graph.add_edge(START, "reference")

        # 两者完成后汇合到 verify（LangGraph 会等待所有入边完成）
        graph.add_edge("ocr", "verify")
        graph.add_edge("reference", "verify")

        # 串行后续步骤
        graph.add_edge("verify", "reproduce")
        graph.add_edge("reproduce", "structure")
        graph.add_edge("structure", END)

        return graph.compile()

    def _fallback_parse(self, file_path: str, subject: str) -> dict:
        """降级方案：直接用 FileReader + LLM 解析（复用现有逻辑）"""
        try:
            text = FileReader.read_file(file_path)
            if not text.strip():
                return {"subject": subject, "questions": []}

            from agents.base.prompts import TEXT_PARSE_PROMPT
            chain = TEXT_PARSE_PROMPT | self.llm | StrOutputParser()
            json_result = chain.invoke({
                "text": text[:8000],
                "subject": subject,
                "format_instructions": get_format_instructions(),
            })

            parsed_data = parse_and_validate(json_result)
            questions = parsed_data.get("questions") or []
            for q in questions:
                normalize_question_data(q)

            return parsed_data
        except Exception as e:
            print(f"[FileAgent] 降级解析也失败: {e}")
            return {"subject": subject, "questions": []}
