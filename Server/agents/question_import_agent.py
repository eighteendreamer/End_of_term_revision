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
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agents.base.prompts import (IMPORT_SYSTEM, PAGE_USER, REPAIR_USER,
                                 TEXT_USER)
from services.llm_client import LLMClient
from services.question_chunker import (Batch, QuestionBlock, pack_batches,
                                       split_batch, split_blocks)
from services.question_schema import parse_questions

logger = logging.getLogger(__name__)

CONCURRENCY = 3
# 模型返回的题干通常保留原文题号（"15. …"），这是判断"漏了哪几题"的唯一线索
STEM_NUMBER_RE = re.compile(r"^\s*(\d{1,3})[.、]")
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
    starved: bool = False
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
                 for i, batch in enumerate(
                     pack_batches(blocks,
                                  max_questions=self.client.questions_per_batch))]
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

        self._repair_flagged(outcome)
        outcome.repairs = sorted(set(outcome.repairs))
        return outcome

    def _repair_flagged(self, outcome: ImportOutcome) -> None:
        """
        返回前端前的拦截复查：代码查问题 → 只修有问题的题 → 代码再拦截。

        第一层与第二层拦截都是纯代码；中间最多一轮模型修正，且只送有问题的题、
        只改标了问题的字段。修不好的发现写进疑点随结果返回，由人工处理。
        """
        findings = _audit_outcome(outcome)
        if not findings:
            return
        for index, items in findings.items():
            issues = outcome.issues.setdefault(index, [])
            issues.extend(item for item in items if item not in issues)

        listing = "\n\n".join(
            "题号 %s\n题干：%s\n选项：%s\n当前答案：%s\n当前解析：%s\n问题：%s" % (
                question.get("number") or index + 1,
                str(question.get("question") or "").strip(),
                "；".join(question.get("options") or []) or "无",
                str(question.get("answer") or "").strip() or "（空）",
                str(question.get("analysis") or "").strip() or "（空）",
                "、".join(items))
            for index, question, items in
            ((index, outcome.questions[index], items)
             for index, items in findings.items()))
        try:
            result = self.client.complete_json(
                IMPORT_SYSTEM,
                REPAIR_USER.format(subject=outcome.subject, questions=listing),
                self.client.output_budget(len(findings)))
        except Exception as exc:
            logger.warning("复查修正失败: %s", exc)
            outcome.errors.append("复查修正失败: %s" % exc)
            return

        repaired = parse_questions(result.text)
        by_number = {str(q.get("number")): q for q in repaired["questions"]
                     if q.get("number")}
        by_stem = {str(q.get("question") or "").strip(): q
                   for q in repaired["questions"]}
        fixed = 0
        for index, question in enumerate(outcome.questions):
            if index not in findings:
                continue
            key = str(question.get("number") or "")
            hit = by_number.get(key) or by_stem.get(
                str(question.get("question") or "").strip())
            if not hit:
                continue
            answer = str(hit.get("answer") or "").strip()
            analysis = str(hit.get("analysis") or "").strip()
            stem = str(hit.get("question") or "").strip()
            if answer and answer != str(question.get("answer") or "").strip():
                question["answer"] = answer
            if analysis and analysis != str(question.get("analysis") or "").strip():
                question["analysis"] = analysis
            if stem and "答案" not in stem and stem != str(
                    question.get("question") or "").strip():
                question["question"] = stem
            fixed += 1

        remaining = _audit_outcome(outcome)
        for index, items in findings.items():
            issues = outcome.issues.get(index)
            if not issues:
                continue
            if index in remaining:
                issues.extend(item for item in remaining[index] if item not in issues)
            else:
                cleaned = [item for item in issues if item not in items]
                if cleaned:
                    outcome.issues[index] = cleaned
                else:
                    outcome.issues.pop(index, None)
        if fixed:
            outcome.repairs.append("复查修正 %d 题" % fixed)
        for index, items in remaining.items():
            outcome.errors.append(
                "第 %s 题复查后仍存在问题：%s" % (
                    outcome.questions[index].get("number") or index + 1,
                    "、".join(items)))

    def _execute(self, plan: BatchPlan, subject: str, prompt_for: PromptFor,
                 index: int, depth: int,
                 budget: Optional[int] = None,
                 refill: bool = True) -> Tuple[Dict[str, Any], BatchMeta]:
        """
        跑一批；被输出上限截断就重试，模型少给题就按题号回补一次。

        文本批次按题号二分（题数是精确已知量，拆小就能装下）；
        整页图片批次拆不动，只能加码输出预算整页重问一次，且只重问一次。
        """
        meta = BatchMeta(batches=1)
        prompt = prompt_for(plan, subject, index)
        max_tokens = budget or self.client.output_budget(plan.question_count)

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
        meta.starved = result.starved

        if (cut and budget is None and not plan.blocks
                and depth < MAX_SPLIT_DEPTH):
            bigger = self.client.budget_for_retry(max_tokens)
            if bigger > max_tokens:
                retry_parsed, retry_meta = self._execute(
                    plan, subject, prompt_for, index, depth + 1, bigger)
                meta.batches += retry_meta.batches
                meta.retried = 1 + retry_meta.retried
                if _better(retry_parsed, retry_meta, parsed):
                    meta.errors.extend(retry_meta.errors)
                    meta.missing += retry_meta.missing
                    meta.truncated = retry_meta.truncated
                    meta.starved = retry_meta.starved
                    return retry_parsed, meta

        if not cut or depth >= MAX_SPLIT_DEPTH or not plan.blocks:
            if plan.blocks and not cut and not meta.starved and refill:
                missing = _missing_blocks(plan, parsed)
                if missing:
                    extra, extra_meta = self._refill(plan, subject, prompt_for,
                                                     index, missing)
                    meta.batches += extra_meta.batches
                    meta.retried += 1
                    meta.errors.extend(extra_meta.errors)
                    parsed = _merge_batch(parsed, extra)
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

    def _refill(self, plan: BatchPlan, subject: str, prompt_for: PromptFor,
                index: int,
                missing: List[QuestionBlock]) -> Tuple[Dict[str, Any], BatchMeta]:
        """
        只把模型漏掉的那几题再问一次。

        整批重送会把已经拿到的题再要一遍（入库就重复），所以这里只送缺失题号；
        也不递归回补——一轮补不齐就是模型给不出，剩下的差额记账交给用户。
        """
        meta = BatchMeta(batches=1)
        sub = BatchPlan(label=plan.label, blocks=missing)
        try:
            result = self.client.complete_json(
                IMPORT_SYSTEM, prompt_for(sub, subject, index),
                self.client.output_budget(sub.question_count))
        except Exception as exc:
            logger.warning("批次 %s 回补失败: %s", plan.label, exc)
            return dict(_EMPTY_BATCH), meta
        parsed = parse_questions(result.text)
        meta.truncated = result.truncated or parsed.get("truncated", False)
        meta.starved = result.starved
        return parsed, meta


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
    # 思考型模型把整批预算吃光时，"未解析出题目"是没有处置方向的废话
    reason = (f"输出预算全被模型思考占满，没有返回任何内容；请在「AI 模型配置」把"
              f"最大输出 token 调大，或改用非思考模型") if meta.starved else ""
    if plan.blocks:
        wanted = {_main_number(block.number) for block in plan.blocks}
        wanted.discard("")
        returned = _returned_numbers(parsed)
        if wanted and returned:
            # 模型按小问拆分（15(1)、15(2)）会让返回题数多于送出块数，数量差
            # 不是守恒判据；只有"某个原文题号一题都没回"才是真缺。
            lost = wanted - returned
            meta.missing = len(lost)
            if lost:
                meta.errors.append("%s 缺第 %s 题" % (
                    plan.label, "、".join(sorted(lost, key=int))))
        elif got < len(plan.blocks):
            meta.missing = len(plan.blocks) - got
            meta.errors.append(f"{plan.label} 送 {len(plan.blocks)} 题只回来 {got} 题"
                               + (f"：{reason}" if reason else ""))
    elif got == 0:
        meta.errors.append(reason or f"{plan.label} 未解析出任何题目")


def _main_number(raw: Any) -> str:
    """取题号的主编号：15(2)(ⅱ) → 15。模型按小问拆分时只有主号可比对。"""
    match = re.match(r"\s*(\d{1,3})", str(raw or ""))
    return match.group(1) if match else ""


def _returned_numbers(parsed: Dict[str, Any]) -> set:
    """回来的题覆盖了哪些主编号；优先用 JSON 的 no，退而扫题干开头的题号。"""
    numbers = set()
    for question in parsed["questions"]:
        number = _main_number(question.get("number"))
        if not number:
            match = STEM_NUMBER_RE.match(str(question.get("question") or ""))
            number = match.group(1) if match else ""
        if number:
            numbers.add(number)
    return numbers


def _missing_blocks(plan: BatchPlan, parsed: Dict[str, Any]) -> List[QuestionBlock]:
    """
    按原文主编号找出模型漏给的题块。

    认不出任何题号时返回空：宁可少补一次，也不能把同一批题重复审进库里。
    """
    returned = _returned_numbers(parsed)
    if not returned:
        return []
    return [block for block in plan.blocks
            if _main_number(block.number) and _main_number(block.number) not in returned]


_PLACEHOLDER_ANALYSIS = "（原文未提供解析，待补充）"


def _audit_question(question: Dict[str, Any]) -> List[str]:
    """
    单题的代码级复查。只查得出结构问题：语义对错由模型复查轮处理。

    每条发现都会展示在预览疑点里；有发现才触发修正轮。
    """
    findings: List[str] = []
    qtype = question.get("type")
    options = [str(option) for option in (question.get("options") or [])]
    answer = str(question.get("answer") or "").strip()
    analysis = str(question.get("analysis") or "").strip()
    stem = str(question.get("question") or "").strip()

    if not answer:
        findings.append("答案缺失")
    if not analysis or analysis == _PLACEHOLDER_ANALYSIS:
        findings.append("解析缺失")

    letters = []
    for option in options:
        match = re.match(r"^([A-Z])[.、．]", option.strip())
        if match:
            letters.append(match.group(1))
    if qtype in ("single", "multiple") and options:
        if answer:
            picked = re.findall(r"[A-Z]", answer.upper())
            if not picked or any(letter not in letters for letter in picked):
                findings.append("答案与选项对不上")
            elif qtype == "multiple" and picked != sorted(set(picked)):
                findings.append("多选答案未去重排序")
        if len(options) < 2:
            findings.append("选项数量不足")
    if qtype == "judge" and answer and answer not in ("对", "错"):
        findings.append("判断题答案应为对或错")
    if any("答案" in option or "正确答案" in option for option in options):
        findings.append("选项里混入了答案字样")
    if "答案：" in stem or "正确答案" in stem:
        findings.append("题干里混入了答案字样")
    return findings


def _audit_outcome(outcome: ImportOutcome) -> Dict[int, List[str]]:
    return {index: _audit_question(question)
            for index, question in enumerate(outcome.questions)
            if _audit_question(question)}


def _better(candidate: Dict[str, Any], candidate_meta: BatchMeta,
            current: Dict[str, Any]) -> bool:
    """重试值不值得采用：题更多，或题数相同但输出没被截断（字段更完整）。"""
    got, now = len(candidate["questions"]), len(current["questions"])
    return got > now or (got == now and not candidate_meta.truncated)


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
