# -*- coding: utf-8 -*-
"""
模型 JSON 输出的容错解析底座。

设计前提：提示词里再多次强调"必须返回合法 JSON"也挡不住模型输出围栏、
串内裸换行和 LaTeX 单反斜杠，所以这些一律在代码里修，不指望模型。
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# JSON 字符串内允许出现的转义字符（含反斜杠自身与 \/）
_VALID_ESCAPES = set('"\\/bfnrt')
# 源串里已有 1 个反斜杠，再补 1 个才凑成合法转义
_EXTRA_BACKSLASH = "\\"

_FENCE_HEAD = re.compile(r"^\s*```(?:json|JSON)?\s*\n?")
_FENCE_TAIL = re.compile(r"\n?```\s*$")

# 串内裸控制字符 → 合法转义
_CONTROL_MAP = {
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def strip_code_fence(text: str) -> Tuple[str, bool]:
    """剥掉 ```json ... ``` 围栏。返回 (正文, 是否命中修复)。"""
    stripped = _FENCE_HEAD.sub("", text, count=1)
    stripped = _FENCE_TAIL.sub("", stripped, count=1)
    if stripped != text:
        return stripped.strip(), True
    return text, False


def slice_first_balanced(text: str, open_char: str = "{") -> Tuple[str, bool]:
    """
    截取第一个括号平衡的片段，丢掉前后缀的解说文字。
    字符串字面量内和转义符不参与配对判断。
    """
    close_char = {"{": "}", "[": "]"}[open_char]
    start = text.find(open_char)
    if start < 0:
        return text, False

    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                trimmed = start != 0 or i + 1 != len(text.rstrip())
                return text[start:i + 1], trimmed

    # 未闭合（输出被截断）：返回从起点到末尾，交给补全逻辑
    return text[start:], True


def escape_control_chars(text: str) -> Tuple[str, bool]:
    """把字符串字面量内部的裸换行/回车/制表符转成合法转义序列。"""
    out: List[str] = []
    in_string = False
    escaped = False
    changed = False

    for ch in text:
        if in_string:
            if escaped:
                escaped = False
                out.append(ch)
                continue
            if ch == "\\":
                escaped = True
                out.append(ch)
                continue
            if ch == '"':
                in_string = False
                out.append(ch)
                continue
            if ch in _CONTROL_MAP:
                out.append(_CONTROL_MAP[ch])
                changed = True
                continue
            if ord(ch) < 0x20:
                out.append("\\u{:04x}".format(ord(ch)))
                changed = True
                continue
            out.append(ch)
        else:
            if ch == '"':
                in_string = True
            out.append(ch)

    return "".join(out), changed


def fix_invalid_escapes(text: str) -> Tuple[str, bool]:
    """
    LaTeX 内容里 `\\frac` 常被模型写成单反斜杠形式，而 `\\f` 在 JSON 里是换页符、
    `\\a` 直接非法。合法转义原样保留，非法转义补一个反斜杠。
    """
    out: List[str] = []
    i = 0
    changed = False
    in_string = False
    escaped = False

    while i < len(text):
        ch = text[i]

        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            i += 1
            continue

        if escaped:
            escaped = False
            if ch in _VALID_ESCAPES:
                out.append(ch)
            elif ch == "u" and re.match(r"[0-9a-fA-F]{4}", text[i + 1:i + 5]):
                out.append(ch)
            else:
                out.append(_EXTRA_BACKSLASH)
                out.append(ch)
                changed = True
            i += 1
            continue

        if ch == '"':
            in_string = False
            out.append(ch)
            i += 1
            continue

        if ch == "\\":
            escaped = True
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        i += 1

    return "".join(out), changed


def _scan_state(text: str) -> Tuple[List[str], bool, bool]:
    """返回 (待闭合栈, 是否停在字符串内, 是否停在转义符后)。"""
    stack: List[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in "}]":
            if stack and stack[-1] == ch:
                stack.pop()
    return stack, in_string, escaped


def _with_closures(text: str) -> str:
    """把残缺文本补成括号平衡的形式。"""
    stack, in_string, escaped = _scan_state(text)
    if escaped:
        text = text[:-1]
    if in_string:
        text += '"'
    stack, _, _ = _scan_state(text)
    return text + "".join(reversed(stack))


def close_truncated(text: str) -> Tuple[str, bool]:
    """
    给被 max_tokens 截断的输出补全收尾。

    候选顺序刻意"先丢尾巴再补全"：优先退到最后一个已闭合的对象，
    因为把半道题补成合法 JSON 收进题库，比少一道题更坏。
    只有在前一种切法都解不通时，才退回"整串直接补闭合"。
    """
    if not text:
        return text, False

    stack, in_string, escaped = _scan_state(text)
    if not stack and not in_string and not escaped:
        return text, False

    candidates: List[str] = []
    for boundary in _trim_boundaries(text):
        candidates.append(_with_closures(text[:boundary]))
    candidates.append(_with_closures(text))

    for candidate in candidates:
        try:
            json.loads(candidate)
            return candidate, True
        except json.JSONDecodeError:
            continue

    return candidates[-1], True


def _trim_boundaries(text: str) -> List[int]:
    """按"丢弃最少"排序的回退点：最后一个已闭合对象之后、最后一个逗号之后。"""
    boundaries: List[int] = []
    for closer in ("}", "]"):
        index = text.rfind(closer)
        if index > 0:
            boundaries.append(index + 1)
    comma = text.rfind(",")
    if comma > 0:
        boundaries.append(comma)
    return sorted(set(boundaries), reverse=True)


def loads_lenient(raw: str) -> Tuple[Any, List[str], Optional[str]]:
    """
    宽松解析模型输出。

    :return: (对象, 命中的修复项列表, 失败原因)。对象为 None 时表示彻底失败。
    """
    repairs: List[str] = []
    if not raw:
        return None, repairs, "空响应"

    text = raw.strip()
    if not text:
        return None, repairs, "空响应"

    text, fenced = strip_code_fence(text)
    if fenced:
        repairs.append("strip_code_fence")

    try:
        return json.loads(text), repairs, None
    except json.JSONDecodeError:
        pass

    sliced, sliced_changed = slice_first_balanced(text, "{")
    if not sliced_changed:
        sliced, changed = slice_first_balanced(text, "[")
        sliced_changed = sliced_changed or changed
    if sliced_changed:
        repairs.append("slice_balanced")

    candidates: List[str] = [sliced]

    escaped_text, esc_changed = escape_control_chars(sliced)
    if esc_changed:
        repairs.append("escape_control_chars")
        candidates.append(escaped_text)

    fixed, esc_fixed = fix_invalid_escapes(escaped_text if esc_changed else sliced)
    if esc_fixed:
        repairs.append("fix_invalid_escapes")
        candidates.append(fixed)

    closed, closed_changed = close_truncated(candidates[-1])
    if closed_changed:
        repairs.append("close_truncated")
        candidates.append(closed)

    errors: List[str] = []
    for candidate in candidates:
        try:
            return json.loads(candidate), repairs, None
        except json.JSONDecodeError as exc:
            errors.append(exc.msg)

    return None, repairs, "；".join(errors[:2]) or "无法解析"


def iter_question_objects(raw: str) -> Tuple[List[Dict[str, Any]], int]:
    """
    逐题恢复：从原始文本里把 "questions" 数组内的每个对象单独解出来，
    坏的丢掉、好的留下。这是"全有或全无"的替代方案。

    未闭合的尾部对象一律明确计为丢失，不做半题恢复——半道题比少一道题更坏，
    它会带着空答案进库。

    :return: (题目字典列表, 被放弃的对象个数)
    """
    if not raw:
        return [], 0

    text, _ = strip_code_fence(raw.strip())
    anchor = text.find('"questions"')
    bracket = text.find("[", anchor) if anchor >= 0 else text.find("[")
    if bracket < 0:
        return [], 0

    decoder = json.JSONDecoder()
    cursor = bracket + 1
    collected: List[Dict[str, Any]] = []
    dropped = 0

    while cursor < len(text):
        while cursor < len(text) and text[cursor] in " \r\n\t,":
            cursor += 1
        if cursor >= len(text) or text[cursor] == "]":
            break
        if text[cursor] != "{":
            break

        end = _scan_object_end(text, cursor)
        if end < 0:
            dropped += 1
            break

        parsed = _try_decode_object(decoder, text[cursor:end + 1])
        if parsed is None:
            dropped += 1
            break

        collected.append(parsed)
        cursor = end + 1

    return collected, dropped


def _scan_object_end(text: str, start: int) -> int:
    """返回与 text[start]=='{' 配对的 '}' 下标，找不到返回 -1。"""
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _try_decode_object(decoder: json.JSONDecoder, chunk: str) -> Optional[Dict[str, Any]]:
    """先整体解，再逐层修复；全失败返回 None。"""
    for candidate in _candidate_repairs(chunk):
        try:
            obj, _ = decoder.raw_decode(candidate)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def _candidate_repairs(chunk: str) -> List[str]:
    out = [chunk]

    escaped, esc_changed = escape_control_chars(chunk)
    if esc_changed:
        out.append(escaped)

    fixed, fix_changed = fix_invalid_escapes(escaped if esc_changed else chunk)
    if fix_changed:
        out.append(fixed)

    return out
