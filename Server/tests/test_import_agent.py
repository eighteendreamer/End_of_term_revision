# -*- coding: utf-8 -*-
"""
导入 Agent 的集成测试：用假客户端驱动，不触达任何真实模型。

覆盖的是这次改造的核心承诺：批次顺序、截断二分重试、单批失败不拖垮整次导入、
问题清单按最终题号对齐、进度回调可用。
"""
import json
import os
import sys
import time
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from agents.question_import_agent import QuestionImportAgent
from services.llm_client import LLMResult


class ModelError(Exception):
    pass


@dataclass
class Scripted:
    """一条脚本化的模型响应。"""
    text: str = ""
    finish_reason: str = "stop"
    raises: Optional[Exception] = None
    delay: float = 0.0


@dataclass
class FakeClient:
    script: List[Scripted]
    calls: List[Dict[str, Any]] = field(default_factory=list)
    budget: int = 2048
    max_output_tokens: int = 8192

    def output_budget(self, question_count: int, per_question: int = 700) -> int:
        return self.budget

    def budget_for_retry(self, budget: int) -> int:
        return min(max(budget * 2, budget + 1024), self.max_output_tokens)

    def complete_json(self, system, user, max_tokens,
                      images: Optional[List[str]] = None) -> LLMResult:
        self.calls.append({"user": user, "max_tokens": max_tokens,
                           "images": images or []})
        if not self.script:
            return LLMResult(text='{"questions": []}', finish_reason="stop",
                             model="fake")
        item = self.script.pop(0)
        if item.delay:
            time.sleep(item.delay)
        if item.raises:
            raise item.raises
        return LLMResult(text=item.text, finish_reason=item.finish_reason,
                         model="fake", truncated=item.finish_reason == "length")


def _questions(items: List[str]) -> str:
    return json.dumps({
        "subject": "数学",
        "questions": [
            {"type": "single", "question": q, "options": ["A. 一", "B. 二"],
             "answer": "A", "analysis": "因为甲"} for q in items
        ],
    }, ensure_ascii=False)


def _numbered_text(count: int) -> str:
    return "\n".join(f"{i}. 这是第{i}题的题干内容" for i in range(1, count + 1))


class TestTextImport(unittest.TestCase):

    def test_single_batch_returns_all_questions(self):
        client = FakeClient([Scripted(text=_questions(["1. 甲", "2. 乙"]))])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(2), "数学")
        self.assertEqual(outcome.count, 2)
        self.assertEqual(outcome.batches, 1)
        self.assertEqual(client.calls[0]["max_tokens"], 2048)

    def test_batch_order_preserved_despite_completion_order(self):
        # 9 题会装箱成 8+1 两批；让第一批后完成，验证合并仍按原文顺序
        client = FakeClient([
            Scripted(text=_questions([f"{i}. 题{i}" for i in range(1, 9)]), delay=0.08),
            Scripted(text=_questions(["9. 题9"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(9), "数学")
        self.assertEqual(outcome.count, 9)
        self.assertEqual(outcome.questions[0]["question"], "1. 题1")
        self.assertEqual(outcome.questions[-1]["question"], "9. 题9")

    def test_prompt_carries_subject_and_text(self):
        client = FakeClient([Scripted(text=_questions(["1. 甲"]))])
        QuestionImportAgent(client).import_text(_numbered_text(1), "物理")
        self.assertIn("物理", client.calls[0]["user"])
        self.assertIn("1. 这是第1题", client.calls[0]["user"])

    def test_truncated_batch_is_split_and_retried(self):
        client = FakeClient([
            Scripted(text='{"questions": [{"type": "single"', finish_reason="length"),
            Scripted(text=_questions(["1. 甲"])),
            Scripted(text=_questions(["2. 乙"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(2), "数学")
        self.assertEqual(outcome.retried_batches, 1)
        self.assertEqual(outcome.batches, 3)
        self.assertTrue(outcome.truncated)
        self.assertEqual([q["question"] for q in outcome.questions], ["1. 甲", "2. 乙"])

    def test_failing_batch_does_not_kill_the_import(self):
        client = FakeClient([
            Scripted(raises=ModelError("HTTP 429")),
            Scripted(text=_questions(["2. 乙"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(9), "数学")
        self.assertGreaterEqual(len(outcome.errors), 1)
        self.assertIn("429", outcome.errors[0])
        self.assertGreaterEqual(outcome.count, 1)

    def test_issues_keyed_by_final_index(self):
        payload = {"subject": "数学", "questions": [
            {"type": "single", "question": "1. 甲", "options": ["A. 一", "B. 二"],
             "answer": "A", "analysis": "完整解析"},
            {"type": "single", "question": "2. 乙", "options": ["A. 一", "B. 二"],
             "answer": "A"},
        ]}
        client = FakeClient([Scripted(text=json.dumps(payload, ensure_ascii=False))])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(2), "数学")
        self.assertEqual(outcome.count, 2)
        self.assertIn(1, outcome.issues)
        self.assertIn("解析缺失", outcome.issues[1])
        self.assertNotIn(0, outcome.issues)

    def test_empty_text_rejected(self):
        with self.assertRaises(ValueError):
            QuestionImportAgent(FakeClient([])).import_text("   ", "数学")


class TestImageImport(unittest.TestCase):

    def test_one_batch_per_page(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 甲"])),
            Scripted(text=_questions(["2. 乙"])),
        ])
        outcome = QuestionImportAgent(client).import_images(
            ["data:image/png;base64,AAA", "data:image/png;base64,BBB"], "数学")
        self.assertEqual(outcome.batches, 2)
        self.assertEqual(outcome.count, 2)
        self.assertEqual(len(client.calls[0]["images"]), 1)

    def test_page_prompt_states_position(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 甲"])),
            Scripted(text=_questions(["2. 乙"])),
        ])
        QuestionImportAgent(client).import_images(["a", "b"], "数学")
        self.assertIn("第 1 页（共 2 页）", client.calls[0]["user"])
        self.assertIn("第 2 页（共 2 页）", client.calls[1]["user"])

    def test_no_images_rejected(self):
        with self.assertRaises(ValueError):
            QuestionImportAgent(FakeClient([])).import_images([], "数学")


class TestProgress(unittest.TestCase):

    def test_progress_reaches_total(self):
        seen: List[tuple] = []
        client = FakeClient([
            Scripted(text=_questions(["1. 甲"])),
            Scripted(text=_questions(["2. 乙"])),
        ])
        QuestionImportAgent(client, on_progress=lambda d, t, c: seen.append((d, t, c)))\
            .import_text(_numbered_text(9), "数学")
        self.assertTrue(seen)
        self.assertEqual(max(d for d, _t, _c in seen), seen[0][1])
        self.assertEqual(seen[-1][2], 2)


class TestPageTruncationRetry(unittest.TestCase):
    """
    整页图片没有题号可拆，被输出上限截断时只能整页重试。

    文件导入现在全部走这条路，一页密题（语文现代文阅读、英语阅读理解）
    最容易撑爆预算；不重试就等于这一页永久缺题。
    """

    def test_truncated_page_is_retried_with_a_bigger_budget(self):
        client = FakeClient([
            Scripted(text='{"questions": [{"type": "single", "question": "1. 甲"',
                     finish_reason="length"),
            Scripted(text=_questions(["1. 甲", "2. 乙", "3. 丙"])),
        ])
        outcome = QuestionImportAgent(client).import_images(["data:image/png;base64,A"],
                                                            "数学")
        self.assertEqual(client.calls[1]["max_tokens"], 4096,
                         "重试要把输出预算加大再问一次")
        self.assertEqual(outcome.retried_batches, 1)
        self.assertEqual(outcome.batches, 2)
        self.assertEqual(outcome.count, 3)
        self.assertFalse(outcome.truncated, "重试拿到了完整输出，就不该再报截断")

    def test_same_count_prefers_the_untruncated_attempt(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 甲", "2. 乙"]), finish_reason="length"),
            Scripted(text=_questions(["1. 甲", "2. 乙"])),
        ])
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        self.assertEqual(outcome.count, 2)
        self.assertFalse(outcome.truncated)

    def test_keeps_first_result_when_retry_is_worse(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 甲", "2. 乙"]), finish_reason="length"),
            Scripted(text=_questions(["1. 甲"]), finish_reason="length"),
        ])
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        self.assertEqual(outcome.count, 2)
        self.assertEqual(outcome.retried_batches, 1)
        self.assertTrue(outcome.truncated)

    def test_no_retry_when_budget_already_at_model_cap(self):
        client = FakeClient([
            Scripted(text='{"questions": [{"type": "single"', finish_reason="length"),
        ], budget=8192, max_output_tokens=8192)
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        self.assertEqual(len(client.calls), 1, "已到模型上限还重试只会白烧一次调用")
        self.assertEqual(outcome.retried_batches, 0)
        self.assertTrue(outcome.truncated)

    def test_retry_only_happens_once_per_page(self):
        client = FakeClient([
            Scripted(text='{"questions": [{"type": "single"', finish_reason="length"),
            Scripted(text='{"questions": [{"type": "single"', finish_reason="length"),
        ])
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        self.assertEqual(len(client.calls), 2, "重试要有界，不能对同一页无限加码")
        self.assertTrue(outcome.truncated)


class TestStarvedPage(unittest.TestCase):
    """思考型模型把预算吃光、一个字不返回时，报错要给出可执行的处置方向。"""

    def test_empty_output_reports_budget_not_generic_failure(self):
        client = FakeClient([
            Scripted(text="", finish_reason="length"),
            Scripted(text="", finish_reason="length"),
        ])
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        joined = "；".join(outcome.errors)
        self.assertEqual(outcome.count, 0)
        self.assertIn("输出预算", joined,
                      "只说「未解析出任何题目」用户不知道该做什么")
        self.assertIn("思考", joined)

    def test_starved_page_still_gets_one_bigger_retry(self):
        client = FakeClient([
            Scripted(text="", finish_reason="length"),
            Scripted(text=_questions(["第1题"]), finish_reason="stop"),
        ])
        outcome = QuestionImportAgent(client).import_images(["a"], "数学")
        self.assertEqual(len(client.calls), 2)
        self.assertGreater(client.calls[1]["max_tokens"], client.calls[0]["max_tokens"])
        self.assertEqual(outcome.count, 1, "加码后拿到题就不该再报缺题")
        self.assertEqual(outcome.errors, [])


class TestMissingNumberRefill(unittest.TestCase):
    """
    模型少给题时按原文题号回补一次。

    真机实测：送 8 题回来 6 题是常态（共享同一段阅读材料的题被模型合并）。
    只记账不回补，"入库题数 = 原文题数"这条验收线永远达不到。
    """

    def test_short_batch_is_refilled_for_the_missing_numbers(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 第一题题干", "2. 第二题题干",
                                      "3. 第三题题干"])),
            Scripted(text=_questions(["4. 第四题题干", "5. 第五题题干"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(5), "数学")
        self.assertEqual(outcome.count, 5, "回补后应凑齐送进去的 5 题")
        self.assertEqual(outcome.missing, 0)
        self.assertEqual(len(client.calls), 2)
        # 回补批次只带缺失的题号，不能把整批重送一遍
        self.assertNotIn("1. 这是第1题", client.calls[1]["user"])
        self.assertIn("5. 这是第5题", client.calls[1]["user"])

    def test_refill_is_bounded_to_one_pass(self):
        client = FakeClient([
            Scripted(text=_questions(["1. 第一题题干"])),
            Scripted(text=_questions(["2. 第二题题干"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(5), "数学")
        self.assertEqual(len(client.calls), 2, "回补只跑一轮，不能递归追打")
        self.assertEqual(outcome.missing, 3, "补不齐的差额仍要记账")
        self.assertTrue(any("缺第" in e for e in outcome.errors),
                        "要点名缺的是哪几题，而不是只报一个差额")

    def test_sub_question_split_is_not_missing(self):
        """提示词要求把 15(1)/15(2) 拆成独立题目，拆分不能被当成缺题再补一遍。"""
        payload = json.dumps({"questions": [
            {"no": no, "type": "major", "question": f"第 {no} 小问",
             "options": [], "answer": "见解析", "analysis": "略"}
            for no in ("14", "15(1)", "15(2)", "16")]}, ensure_ascii=False)
        client = FakeClient([Scripted(text=payload)])
        source = "\n".join(f"{n}. 这是第{n}题的题干内容" for n in (14, 15, 16))
        outcome = QuestionImportAgent(client).import_text(source, "数学")
        self.assertEqual(len(client.calls), 1, "15 已被 15(1)/15(2) 覆盖，不该再补问")
        self.assertEqual(outcome.missing, 0)
        self.assertEqual(outcome.count, 4)

    def test_no_refill_when_numbers_are_not_recognisable(self):
        """题干里没有题号时对不上号，回补会把同一批重复审进去造成重复入库。"""
        client = FakeClient([
            Scripted(text=_questions(["没有标号的题干甲", "没有标号的题干乙"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(4), "数学")
        self.assertEqual(len(client.calls), 1, "认不出题号就不该回补")
        self.assertEqual(outcome.count, 2)
        self.assertEqual(outcome.missing, 2)

    def test_refill_uses_the_no_field_when_stems_drop_the_number(self):
        """真机实测模型返回的英文题干不带题号，此时靠 JSON 里的 no 字段对齐。"""
        def payload(numbers):
            return json.dumps({"questions": [
                {"no": n, "type": "single", "question": f"stem of {n}",
                 "options": ["A. 一", "B. 二"], "answer": "A", "analysis": "因为甲"}
                for n in numbers]}, ensure_ascii=False)

        client = FakeClient([
            Scripted(text=payload(["1", "2", "3"])),
            Scripted(text=payload(["4", "5"])),
        ])
        outcome = QuestionImportAgent(client).import_text(_numbered_text(5), "数学")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(outcome.count, 5)
        self.assertEqual(outcome.missing, 0)
        self.assertNotIn("1. 这是第1题", client.calls[1]["user"],
                         "回补只送缺的 4、5 题")


class TestNumberFieldContract(unittest.TestCase):
    """no/题号 是模型对原文的判断，代码算不出来，所以进 JSON 契约并由代码保留。"""

    def test_normalized_question_keeps_source_number(self):
        from services.question_schema import normalize_question
        kept, _ = normalize_question({"no": "15", "type": "single",
                                      "question": "Which of the following",
                                      "options": ["A. 一", "B. 二"], "answer": "A"})
        self.assertEqual(kept["number"], "15")

    def test_missing_number_does_not_add_noise(self):
        from services.question_schema import normalize_question
        kept, _ = normalize_question({"type": "single", "question": "题干",
                                      "options": ["A. 一", "B. 二"], "answer": "A"})
        self.assertNotIn("number", kept)


if __name__ == "__main__":
    unittest.main(verbosity=2)
