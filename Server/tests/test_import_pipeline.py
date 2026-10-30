# -*- coding: utf-8 -*-
"""
整条导入链路的"题数守恒"验收（离线，不触达任何真实模型）。

验收口径是"入库题数 = 原文题数，且差额原因可见"。真实模型那一半要用户的
base_url/模型名/密钥才能跑；这一半——题号切分、装箱、并发合并、乱输出修复、
逐页渲染成图后的一页一批——全部可以离线证明，所以先离线钉死：

  * EchoClient 会读到自己 prompt 里的题号，然后按题号把题目吐回来。
    于是"原文有几题"是一个独立于代码的已知量，链路任何一处丢题都会暴露。
  * EchoClient 同时故意输出模型真实会犯的错：```json 围栏、前面加一句客套、
    字符串里裸换行、LaTeX 单反斜杠。证明保号靠的是修复器而不是提示词恳求。
"""
import json
import os
import re
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

import fitz  # PyMuPDF

from agents.question_import_agent import QuestionImportAgent
from services.document_renderer import render_to_images
from services.llm_client import LLMResult

_QUESTION_LINE = re.compile(r"^(\d+)[.、．]", re.MULTILINE)


def paper_text(count: int) -> str:
    """构造一份题号连续、带公式和换行的卷子文本。"""
    lines = ["注意事项：本卷共 %d 题，请用黑色字迹作答。" % count]
    for i in range(1, count + 1):
        lines.append(f"{i}. 已知 $a_{{n+1}}=2a_n$，求第 {i} 题的通项公式，")
        lines.append("并说明推导依据。")
    return "\n".join(lines)


def source_numbers(text: str) -> List[int]:
    """独立复算原文题号，作为验收的已知真值。"""
    return [int(m) for m in _QUESTION_LINE.findall(_stem_region(text))]


def _stem_region(prompt: str) -> str:
    """剥掉提示词自带的编号说明，只留下正文区，避免把"1. type 只能取…"当成题。"""
    return prompt.split("输出要求：")[0]


@dataclass
class EchoClient:
    """
    假装自己是模型：从 prompt 里读出题号，逐题返回。

    drop / messy / truncate 三个开关用来复现真实模型会造成的三类事故。
    """
    drop: List[int] = field(default_factory=list)
    messy: bool = True
    truncate_after: Optional[int] = None
    calls: List[Dict[str, Any]] = field(default_factory=list)
    budget: int = 4096
    max_output_tokens: int = 8192
    # 真实客户端按模型上限动态算批大小；假客户端把它钉死，用例语义才稳定
    questions_per_batch: int = 8

    def output_budget(self, question_count: int, per_question: int = 700) -> int:
        return self.budget

    def budget_for_retry(self, budget: int) -> int:
        return min(max(budget * 2, budget + 1024), self.max_output_tokens)

    def complete_json(self, system, user, max_tokens,
                      images: Optional[List[str]] = None) -> LLMResult:
        self.calls.append({"user": user, "max_tokens": max_tokens,
                           "images": images or []})
        if images:
            numbers = self._numbers_from_image_prompt(user)
        else:
            numbers = [int(m) for m in _QUESTION_LINE.findall(_stem_region(user))]
        numbers = [n for n in numbers if n not in self.drop]
        if self.truncate_after is not None:
            numbers = numbers[:self.truncate_after]

        items = [{"type": "单选", "question": f"{n}. 第{n}题题干",
                  "options": {"A": "甲", "B": "乙"}, "answer": "A",
                  "analysis": f"第{n}题：由 $\\frac{{1}}{{2}}$ 得\n分步依据如上"}
                 for n in numbers]
        body = json.dumps({"subject": "数学", "questions": items},
                          ensure_ascii=False)
        if self.messy:
            body = "好的，解析结果如下：\n```json\n" + body + "\n```"
        if self.truncate_after is not None:
            body = body[:len(body) // 2]
            return LLMResult(text=body, finish_reason="length", model="echo",
                             truncated=True)
        return LLMResult(text=body, finish_reason="stop", model="echo")

    @staticmethod
    def _numbers_from_image_prompt(prompt: str) -> List[int]:
        """图片批次读不到文本，题号由测试脚本按页号推断即可。"""
        match = re.search(r"第 (\d+) 页（共 \d+ 页）", prompt)
        page = int(match.group(1)) if match else 1
        return list(range((page - 1) * 3 + 1, page * 3 + 1))


class TestTextChain(unittest.TestCase):
    """文本 → 题号切分 → 装箱 → 并发调用 → 修复 → 合并。"""

    def _run(self, count: int, **kwargs):
        text = paper_text(count)
        client = EchoClient(**kwargs)
        outcome = QuestionImportAgent(client).import_text(text, "数学")
        return text, client, outcome

    def test_5_questions_fully_preserved(self):
        text, _client, outcome = self._run(5)
        self.assertEqual(outcome.count, len(source_numbers(text)))
        self.assertEqual(outcome.dropped, 0)

    def test_20_questions_fully_preserved(self):
        text, client, outcome = self._run(20)
        self.assertEqual(outcome.count, len(source_numbers(text)))
        self.assertGreater(len(client.calls), 1, "20 题必须拆批，不能一次全塞")

    def test_50_questions_fully_preserved_in_original_order(self):
        text, client, outcome = self._run(50)
        expected = source_numbers(text)
        self.assertEqual(outcome.count, len(expected))
        got = [int(re.match(r"^(\d+)", q["question"]).group(1))
               for q in outcome.questions]
        self.assertEqual(got, expected, "并发合并必须保持原文题号顺序")
        self.assertEqual(outcome.batches, len(client.calls))

    def test_garbage_wrapped_output_still_keeps_every_question(self):
        """围栏+客套话+裸换行+单反斜杠 LaTeX 同时出现时仍要一题不丢。"""
        text, _client, outcome = self._run(12, messy=True)
        self.assertEqual(outcome.count, len(source_numbers(text)))
        self.assertTrue(outcome.repairs, "修复器应当被命中，否则说明噪声没进去")

    def test_normalized_fields_are_ready_for_database(self):
        _text, _client, outcome = self._run(3)
        for question in outcome.questions:
            self.assertEqual(question["type"], "single", "中文题型要归一成枚举")
            self.assertIsInstance(question["options"], list)
            self.assertEqual(question["answer"], "A")
            self.assertTrue(question["analysis"].strip())

    def test_model_silently_drops_a_question_is_reported(self):
        """模型少给题时必须能看见差了多少，否则"入库=原文"永远无法核对。"""
        text, _client, outcome = self._run(10, drop=[7])
        self.assertEqual(outcome.count, len(source_numbers(text)) - 1)
        self.assertEqual(outcome.missing, 1)
        self.assertTrue(any("缺第 7 题" in e for e in outcome.errors),
                        "要直接点名缺的是第 7 题，而不是只给一个差额")

    def test_truncated_questions_are_admitted_only_with_visible_doubts(self):
        """
        拆到拆不动时，半截输出里题干完整的题会被收下，但缺的字段必须标成疑点。

        这是"宁缺毋滥"和"能救就救"的边界：题干都被切掉的题直接丢弃（见
        test_import_foundation 的截断用例），题干在、只是答案/解析被切掉的题
        入库但必须在预览里冒红字，不能让用户以为它是完整的。
        """
        text, _client, outcome = self._run(8, truncate_after=1)
        self.assertTrue(outcome.truncated)
        self.assertTrue(outcome.issues, "被切掉字段的题必须带疑点")
        for issue in outcome.issues.values():
            joined = " ".join(issue)
            self.assertTrue(any(key in joined for key in
                                ("答案缺失", "选项", "解析缺失")), issue)


class TestRenderedDocumentChain(unittest.TestCase):
    """PDF → 整页图片 → 一页一批 → 合并（文件导入的真实链路）。"""

    def _make_pdf(self, page_count: int) -> str:
        path = os.path.join(tempfile.mkdtemp(prefix="chain_"), "paper.pdf")
        doc = fitz.open()
        for i in range(page_count):
            page = doc.new_page(width=595, height=842)
            for j in range(3):
                page.insert_text((72, 100 + j * 40),
                                 f"Question {i * 3 + j + 1} stem here", fontsize=12)
        doc.save(path)
        doc.close()
        return path

    def test_every_page_becomes_one_batch_and_all_questions_survive(self):
        pages = render_to_images(self._make_pdf(4))
        self.assertEqual(len(pages), 4)

        client = EchoClient()
        outcome = QuestionImportAgent(client).import_images(
            [p.data_url() for p in pages], "数学")

        self.assertEqual(outcome.batches, 4, "页数即批数，不允许把多页并成一次调用")
        self.assertEqual(outcome.count, 12, "4 页 × 每页 3 题必须一题不丢")
        got = sorted(int(re.match(r"^(\d+)", q["question"]).group(1))
                     for q in outcome.questions)
        self.assertEqual(got, list(range(1, 13)))

    def test_images_reach_the_model_as_data_urls(self):
        pages = render_to_images(self._make_pdf(2))
        client = EchoClient()
        QuestionImportAgent(client).import_images([p.data_url() for p in pages], "数学")
        for call in client.calls:
            self.assertEqual(len(call["images"]), 1)
            self.assertTrue(call["images"][0].startswith("data:image/png;base64,"))

    def test_empty_page_is_named_and_other_pages_survive(self):
        """某一页一道都没识别出来必须点名——图片批次题数不可知，但空结果可判。"""
        pages = render_to_images(self._make_pdf(3))
        client = EchoClient(drop=list(range(4, 7)))  # 第 2 页整体判空
        outcome = QuestionImportAgent(client).import_images(
            [p.data_url() for p in pages], "数学")
        self.assertEqual(outcome.count, 6)
        self.assertTrue(any("page2" in e for e in outcome.errors), outcome.errors)


class TestChunkerBudget(unittest.TestCase):
    """批次大小与输出预算要由代码决定，不能靠模型自觉。"""

    def test_batch_size_stays_within_limit(self):
        client = EchoClient()
        QuestionImportAgent(client).import_text(paper_text(50), "数学")
        for call in client.calls:
            self.assertGreaterEqual(call["max_tokens"], 700,
                                    "每批至少要给一道题的输出预算")

    def test_budget_scales_with_question_count(self):
        class BudgetClient(EchoClient):
            def output_budget(self, question_count, per_question=700):
                return question_count * per_question

        small = BudgetClient()
        QuestionImportAgent(small).import_text(paper_text(50), "数学")
        budgets = [c["max_tokens"] for c in small.calls]
        self.assertGreater(max(budgets), min(budgets),
                           "满批与零头批的输出预算不应相同")


if __name__ == "__main__":
    unittest.main(verbosity=2)
