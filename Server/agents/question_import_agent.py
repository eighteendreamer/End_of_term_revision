# -*- coding: utf-8 -*-
"""
题目导入 Agent —— 文本 / 图片 / 文档 三条入口共用同一套流程。

流程固定为：切成语义批次 → 每批显式给输出预算调用模型 → 读 finish_reason →
被截断就二分重试 → 逐题容错解析 → 按原顺序合并。

三条入口的差别只在"批次怎么来"：
  文本   按题号装箱（question_chunker）
  图片   一张图一批
  文档   整页渲染成图后，一页一批（见 services/document_renderer）
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.base.prompts import IMPORT_SYSTEM, PAGE_USER, TEXT_USER
from services.llm_client import LLMClient
from services.question_chunker import (Batch, QuestionBlock, pack_batches,
                                       split_batch, split_blocks)
from services.question_schema import parse_questions

logger = logging.getLogger(__name__)

CONCURRENCY = 3
MAX_SPLIT_DEPTH = 3
QUESTIONS_PER_PAGE = 6

_EMPTY_BATCH: Dict[str, Any] = {
    "subject": "", "questions": [], "issues": {}, "dropped": 0,
    "repairs": [], "parse_mode": "empty", "truncated": False,
}


@dataclass
class BatchPlan:
    """一次模型调用的输入。blocks 与 images 二选一。"""
    label: str
    blocks: List[QuestionBlock] = field(default_factory=list)
    images: List[str] = field(default_factory=list)

    @property
    def question_count(self) -> int:
        if self.blocks:
            return len(self.blocks)
        return max(1, len(self.images) * QUESTIONS_PER_PAGE)


@dataclass
class BatchMeta:
    batches: int = 0
    retried: int = 0
    truncated: bool = False
    missing: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class ImportOutcome:
    subject: str
    questions: List[Dict[str, Any]] = field(default_factory=list)
    issues: Dict[int, List[str]] = field(default_factory=dict)
    batches: int = 0
    retried_batches: int = 0
    dropped: int = 0
    missing: int = 0
    truncated: bool = False
    repairs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.questions)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "questions": self.questions,
            "issues": self.issues,
            "stats": {
                "batches": self.batches,
                "retried_batches": self.retried_batches,
                "dropped": self.dropped,
                "missing": self.missing,
                "truncated": self.truncated,
                "repairs": self.repairs,
                "errors": self.errors,
            },
        }


PromptFor = Callable[[BatchPlan, str, int], str]


class QuestionImportAgent:
    """把内容变成题目列表。调用方负责挑模型与构造客户端。"""

    def __init__(self, client: LLMClient,
                 on_progress: Optional[Callable[[int, int, int], None]] = None):
        """
        :param client: 已按用户配置构造好的 LLM 客户端
        :param on_progress: 回调 (已完成批次, 总批次, 累计题目数)
        """
        self.client = client
        self.on_progress = on_progress

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------

    def import_text(self, text: str, subject: str) -> ImportOutcome:
        blocks = split_blocks(text)
        if not blocks:
            raise ValueError("没有从文本里识别出任何题号或段落，请确认内容是试题")
        plans = [BatchPlan(label=f"batch{i + 1}", blocks=batch.blocks)
                 for i, batch in enumerate(pack_batches(blocks))]
        return self._run(plans, subject, _text_prompt)

    def import_images(self, data_urls: List[str], subject: str) -> ImportOutcome:
        if not data_urls:
            raise ValueError("没有可识别的页面图片")
        total = len(data_urls)

        def prompt_for(plan: BatchPlan, subj: str, index: int) -> str:
            return PAGE_USER.format(subject=subj, page_no=index + 1, page_total=total)

        plans = [BatchPlan(label=f"page{i + 1}", images=[url])
                 for i, url in enumerate(data_urls)]
        return self._run(plans, subject, prompt_for)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _run(self, plans: List[BatchPlan], subject: str,
             prompt_for: PromptFor) -> ImportOutcome:
        outcome = ImportOutcome(subject=subject)
        results: List[Optional[Tuple[Dict[str, Any], BatchMeta]]] = [None] * len(plans)
        total = len(plans)
        done = 0

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {
                pool.submit(self._execute, plan, subject, prompt_for, index, 0): index
                for index, plan in enumerate(plans)
            }
            for future in as_completed(futures):
                index = futures[future]
                results[index] = future.result()
                done += 1
                if self.on_progress:
                    self.on_progress(done, total, _count(results))

        for entry in results:
            if entry is None:
                continue
            parsed, meta = entry
            outcome.batches += meta.batches
            outcome.retried_batches += meta.retried
            outcome.missing += meta.missing
            outcome.errors.extend(meta.errors)
            outcome.truncated = outcome.truncated or meta.truncated
            _absorb(outcome, parsed)

        outcome.repairs = sorted(set(outcome.repairs))
        return outcome

    def _execute(self, plan: BatchPlan, subject: str, prompt_for: PromptFor,
                 index: int, depth: int) -> Tuple[Dict[str, Any], BatchMeta]:
        """跑一批；被输出上限截断且还能拆，就二分重试。"""
        meta = BatchMeta(batches=1)
        prompt = prompt_for(plan, subject, index)
        max_tokens = self.client.output_budget(plan.question_count)

        try:
            result = self.client.complete_json(
                IMPORT_SYSTEM, prompt, max_tokens, images=plan.images or None)
        except Exception as exc:
            logger.warning("批次 %s 调用失败: %s", plan.label, exc)
            meta.errors.append(f"{plan.label}: {exc}")
            meta.missing = plan.question_count if plan.blocks else 0
            return dict(_EMPTY_BATCH), meta

        parsed = parse_questions(result.text)
        cut = result.truncated or parsed.get("truncated", False)
        meta.truncated = cut

        if not cut or depth >= MAX_SPLIT_DEPTH or not plan.blocks:
            _diagnose(plan, parsed, meta)
            return parsed, meta

        halves = [BatchPlan(label=f"{plan.label}.{i + 1}", blocks=part.blocks)
                  for i, part in enumerate(split_batch(Batch(plan.blocks)))]
        if len(halves) < 2:
            _diagnose(plan, parsed, meta)
            return parsed, meta

        meta.retried = 1
        combined = dict(_EMPTY_BATCH)
        for half in halves:
            sub_parsed, sub_meta = self._execute(half, subject, prompt_for, index,
                                                 depth + 1)
            meta.batches += sub_meta.batches
            meta.retried += sub_meta.retried
            meta.missing += sub_meta.missing
            meta.errors.extend(sub_meta.errors)
            combined = _merge_batch(combined, sub_parsed)
        combined["truncated"] = combined["truncated"] or parsed.get("truncated", False)
        return combined, meta


def _text_prompt(plan: BatchPlan, subject: str, index: int) -> str:
    return TEXT_USER.format(subject=subject, text=Batch(plan.blocks).text)


def _diagnose(plan: BatchPlan, parsed: Dict[str, Any], meta: BatchMeta) -> None:
    """
    把"送进去几题、回来几题"的差额变成可见信息。

    文本批次题号是精确已知量，少回来就是少回来了，必须记账；图片批次读不到
    题数，只能判断整页是否空手而归。不记这笔账，"入库题数 = 原文题数"
    根本无从核对，模型静默少给题会被当成导入成功。
    """
    got = len(parsed["questions"])
    if plan.blocks:
        expected = plan.question_count
        if got < expected:
            meta.missing = expected - got
            meta.errors.append(f"{plan.label} 送 {expected} 题只回来 {got} 题")
    elif got == 0:
        meta.errors.append(f"{plan.label} 未解析出任何题目")


def _merge_batch(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    merged["questions"] = list(base["questions"]) + list(extra["questions"])
    merged["issues"] = dict(base["issues"])
    offset = len(base["questions"])
    for key, value in extra["issues"].items():
        merged["issues"][key + offset] = value
    merged["repairs"] = list(base["repairs"]) + list(extra["repairs"])
    merged["dropped"] = base["dropped"] + extra["dropped"]
    merged["truncated"] = base.get("truncated", False) or extra.get("truncated", False)
    return merged


def _absorb(outcome: ImportOutcome, parsed: Dict[str, Any]) -> None:
    offset = len(outcome.questions)
    outcome.questions.extend(parsed["questions"])
    for key, value in parsed["issues"].items():
        outcome.issues[key + offset] = value
    outcome.dropped += parsed["dropped"]
    outcome.repairs.extend(parsed["repairs"])


def _count(results: List[Optional[Tuple[Dict[str, Any], BatchMeta]]]) -> int:
    return sum(len(entry[0]["questions"]) for entry in results if entry)
