# -*- coding: utf-8 -*-
"""
按题分块与批次装箱。

分块单位是"一道题"而不是"每 8000 字符"：按字符切会把题干和选项劈开，
模型只能猜；按题号切则每批都是语义完整的输入。
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from services.llm_client import BATCH_SIZE_CEILING, estimate_tokens

MAX_QUESTIONS_PER_BATCH = BATCH_SIZE_CEILING
MAX_BATCH_INPUT_TOKENS = 6000
MIN_QUESTIONS_PER_BATCH = 1

# 主题号：行首 1. / 1、/ 1．/ ①
PRIMARY_RE = re.compile(r"^\s*(?:(\d{1,3})\s*[\.、．](?!\d)|([①-⑳]))")
# 小问：（1）/ (1) —— 归属于当前主题号，不另起一题
SUB_RE = re.compile(r"^\s*[（(]\s*\d{1,3}\s*[)）]")


@dataclass
class QuestionBlock:
    number: str
    text: str

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.text)


@dataclass
class Batch:
    blocks: List[QuestionBlock] = field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.blocks)

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)

    @property
    def input_tokens(self) -> int:
        return estimate_tokens(self.text)


def split_blocks(text: str) -> List[QuestionBlock]:
    """
    把整份文本切成按主题号划分的块。

    行首题号才切；小问 (1)(2) 和续行并入当前块。开头没有题号的说明文字
    作为 front matter 挂在第一块上，避免整段丢失。
    """
    lines = (text or "").replace("\r\n", "\n").split("\n")
    blocks: List[QuestionBlock] = []
    current: List[str] = []
    number: Optional[str] = None
    front: List[str] = []

    for line in lines:
        match = PRIMARY_RE.match(line)
        if match:
            if number is None:
                front.extend(current)
            elif current:
                blocks.append(QuestionBlock(number, _join(current)))
            number = match.group(1) or match.group(2)
            current = [line]
            continue

        if current:
            current.append(line)
        else:
            front.append(line)

    if current and number is not None:
        blocks.append(QuestionBlock(number, _join(current)))
    elif front and not blocks:
        front.extend(current)

    preamble = _join(front)
    if preamble and blocks:
        blocks[0] = QuestionBlock(blocks[0].number, preamble + "\n\n" + blocks[0].text)
    elif preamble and not blocks:
        blocks.append(QuestionBlock("", preamble))

    return [b for b in blocks if b.text.strip()]


def pack_batches(blocks: Sequence[QuestionBlock],
                 *, max_questions: int = MAX_QUESTIONS_PER_BATCH,
                 max_input_tokens: int = MAX_BATCH_INPUT_TOKENS) -> List[Batch]:
    """贪心装箱：同时受题量与输入 token 双约束，单题超限则独占一批。"""
    batches: List[Batch] = []
    current = Batch()

    for block in blocks:
        over_capacity = (
            current.size >= max_questions
            or (current.size and current.input_tokens + block.tokens > max_input_tokens)
        )
        if over_capacity:
            batches.append(current)
            current = Batch()
        current.blocks.append(block)

    if current.blocks:
        batches.append(current)
    return batches


def split_batch(batch: Batch) -> List[Batch]:
    """把一批对半拆开，用于模型输出被 max_tokens 截断后的重试。"""
    if batch.size <= MIN_QUESTIONS_PER_BATCH:
        return [batch]
    mid = (batch.size + 1) // 2
    return [Batch(batch.blocks[:mid]), Batch(batch.blocks[mid:])]


def count_source_questions(blocks: Sequence[QuestionBlock]) -> int:
    """原文里到底有多少道题，用于最后核对"入库题数 = 原文题数"。"""
    total = 0
    for block in blocks:
        if block.number:
            total += 1 + len(SUB_RE.findall(block.text)) if _splits_into_sub(block) else 1
        else:
            total += 0
    return total


def _splits_into_sub(block: QuestionBlock) -> bool:
    """
    含小问的块默认仍算一道题（模型可能合并作答）。
    只有判断题/填空题这类成组小问才按小问计数。
    """
    subs = SUB_RE.findall(block.text)
    if len(subs) < 2:
        return False
    return bool(re.search(r"判断|填空|每空|各?1\s*分", block.text))


def _join(lines: List[str]) -> str:
    return "\n".join(lines).strip()
