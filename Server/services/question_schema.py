# -*- coding: utf-8 -*-
"""
题目结构的代码侧规范化与逐题容错解析。

取代原先"整批 jsonschema 校验、一处不合格全部作废"的做法：
单题解不出来只丢那一题，字段能补则补，补不了记进 issues 交给前端展示。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from utils.json_repair import loads_lenient, iter_question_objects

VALID_TYPES = ("single", "multiple", "judge", "fill", "major")

# 模型可能返回的中英/口语题型 → 库内枚举
TYPE_ALIASES: Dict[str, str] = {
    "single": "single", "单选": "single", "单项选择题": "single", "选择": "single",
    "选择题": "single", "choice": "single", "mcq": "single",
    "multiple": "multiple", "多选": "multiple", "多项选择": "multiple",
    "多选题": "multiple", "不定项选择": "multiple",
    "judge": "judge", "判断": "judge", "判断题": "judge", "true_false": "judge",
    "tf": "judge", "boolean": "judge",
    "fill": "fill", "填空": "fill", "填空题": "fill", "主观填空": "fill",
    "major": "major", "大型题": "major", "主观题": "major", "解答": "major",
    "解答题": "major", "计算": "major", "计算题": "major", "证明": "major",
    "证明题": "major", "论述": "major", "简答": "major", "简答题": "major",
    "应用题": "major", "综合题": "major", "问答": "major",
}

_BLANK_RE = re.compile(r"_{3,}|（\s*）|\(\s+\)|\(\s*）")
_OPTION_LABEL_RE = re.compile(r"^\s*([A-Za-z①-⑳])\s*[\.、．:：)]\s*(.*)$")
_LETTER_RE = re.compile(r"[A-H]")

_JUDGE_TRUE = {"对", "正确", "√", "t", "true", "是", "yes"}
_JUDGE_FALSE = {"错", "错误", "×", "f", "false", "否", "no"}


def normalize_type(raw: Any, question: str, options: List[str], answer: str) -> Tuple[str, Optional[str]]:
    """
    把模型给的题型收敛到枚举；给不出可信依据时按选项/答案/空格形态推断。

    :return: (题型, 说明)。说明非 None 表示这是代码推断出来的，不是模型给的。
    """
    key = str(raw or "").strip()
    if key in VALID_TYPES:
        return key, None
    mapped = TYPE_ALIASES.get(key.lower()) or TYPE_ALIASES.get(key)
    if mapped:
        return mapped, f"题型 {key!r} 归一为 {mapped}"

    letters = _answer_letters(answer)
    if options:
        if len(letters) > 1:
            return "multiple", "按多选答案推断题型"
        return "single", "按有选项推断题型"
    if _looks_judgement(answer):
        return "judge", "按判断答案推断题型"
    if _BLANK_RE.search(question or ""):
        return "fill", "按题干空格推断题型"
    return "major", "题型缺失，按大型题兜底"


def _answer_letters(answer: str) -> List[str]:
    return re.findall(_LETTER_RE, (answer or "").upper())


def _looks_judgement(answer: str) -> bool:
    token = (answer or "").strip().lower()
    return token in _JUDGE_TRUE | _JUDGE_FALSE


def normalize_options(raw: Any) -> List[str]:
    """
    选项归一为字符串列表。模型常把它写成 {"A": "...", "B": "..."} 或整段字符串。
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        lines = [ln.strip() for ln in re.split(r"[\r\n]+|；|;", raw) if ln.strip()]
        return lines
    if isinstance(raw, dict):
        ordered = sorted(raw.keys(), key=_option_sort_key)
        return [f"{k}. {raw[k]}".strip() for k in ordered]
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, dict):
                label = item.get("label") or item.get("key") or ""
                body = item.get("text") or item.get("content") or item.get("value") or ""
                out.append(f"{label}. {body}".strip(". "))
            else:
                out.append(str(item).strip())
        return [o for o in out if o]
    return [str(raw)]


def _option_sort_key(label: str):
    """让 A/B/C… 排在前面，①②③ 次之，其余按原序。"""
    text = str(label).strip()
    if len(text) == 1 and "A" <= text.upper() <= "H":
        return (0, ord(text.upper()), "")
    circled = "①②④⑤⑥⑧⑨⑩"
    if text and text[0] in circled:
        return (1, circled.index(text[0]), "")
    return (2, 0, text)


def normalize_answer(raw: Any, qtype: str) -> str:
    """答案统一成字符串；选择题只留字母，多选题排序去重，判断题收敛为 对/错。"""
    text = "" if raw is None else str(raw).strip()
    if not text:
        return ""

    if qtype in ("single", "multiple"):
        letters = _answer_letters(text)
        if letters:
            uniq = sorted(set(letters))
            return ",".join(uniq) if qtype == "multiple" else uniq[0]
        return text

    if qtype == "judge":
        token = text.lower()
        if token in _JUDGE_TRUE:
            return "对"
        if token in _JUDGE_FALSE:
            return "错"
        return text

    return text


def normalize_question(raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """
    规范化单题。

    :return: (题目字典 或 None, 问题清单)。返回 None 表示这一题救不回来。
    """
    issues: List[str] = []
    if not isinstance(raw, dict):
        return None, ["不是对象"]

    question = _first_str(raw, "question", "stem", "title", "content", "题干", "题目")
    if not question:
        return None, ["缺题干"]

    options = normalize_options(_first_key(raw, "options", "option", "choices", "选项"))
    answer = _first_str(raw, "answer", "answers", "正确答案", "答案")
    analysis = _first_str(raw, "analysis", "explanation", "reason", "解析", "答案解析")

    qtype, inferred = normalize_type(
        _first_key(raw, "type", "question_type", "题型"), question, options, answer
    )
    if inferred:
        issues.append(inferred)

    answer = normalize_answer(answer, qtype)
    if not answer:
        issues.append("答案缺失")

    if qtype == "judge":
        options = ["对", "错"]
    elif qtype in ("fill", "major"):
        options = []
    elif qtype in ("single", "multiple") and len(options) < 2:
        issues.append(f"选择题选项仅 {len(options)} 个")
    elif qtype in ("single", "multiple"):
        _assert_option_labels(options, issues)

    if not analysis:
        analysis = "（原文未提供解析，待补充）"
        issues.append("解析缺失")

    if qtype == "single" and answer and len(options) > 1:
        answer = _remap_answer_to_letter(answer, options) or answer

    return {
        "type": qtype,
        "question": question.strip(),
        "options": options,
        "answer": answer.strip(),
        "analysis": analysis.strip(),
        "resources": _normalize_resources(_first_key(raw, "resources", "resource")),
        # 原文题号是模型对原文的判断，代码算不出来；留着才能定位"漏了哪几题"
        **({"number": str(_first_key(raw, "no", "number", "question_number",
                                      "题号", "序号")).strip()}
           if str(_first_key(raw, "no", "number", "question_number",
                             "题号", "序号") or "").strip() else {}),
    }, issues


def _assert_option_labels(options: List[str], issues: List[str]) -> None:
    """选项只剩字母没有内容时提示——这是模型偷懒的典型形态。"""
    empty = [o for o in options if not _OPTION_LABEL_RE.match(o) or
             not _OPTION_LABEL_RE.match(o).group(2).strip()]
    if len(empty) >= max(2, len(options) // 2):
        issues.append("选项疑似只有标号没有内容")


def _remap_answer_to_letter(answer: str, options: List[str]) -> Optional[str]:
    """模型有时把选项正文当答案返回，回填成对应字母。"""
    if _answer_letters(answer):
        return None
    target = answer.strip().rstrip(".")
    for opt in options:
        match = _OPTION_LABEL_RE.match(opt)
        if not match:
            continue
        if match.group(2).strip().rstrip(".") == target:
            return match.group(1).upper()
    return None


def _normalize_resources(raw: Any) -> List[Dict[str, str]]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        out.append({
            "type": str(item.get("type") or "other").strip() or "other",
            "content": content,
            "description": str(item.get("description") or "").strip(),
        })
    return out


def _first_key(data: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _first_str(data: Dict[str, Any], *keys: str) -> str:
    value = _first_key(data, *keys)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def parse_questions(raw_text: str) -> Dict[str, Any]:
    """
    解析模型返回的一批题目。

    :return: {
        "subject": str,
        "questions": [...],   # 已规范化、可直接入库
        "dropped": int,       # 语法上救不回来的对象数
        "issues": {序号: [...]},
        "repairs": [...],     # 命中的修复项
        "parse_mode": "full" | "per_item" | "empty" | "failed",
    }
    """
    result = {
        "subject": "",
        "questions": [],
        "dropped": 0,
        "issues": {},
        "repairs": [],
        "parse_mode": "empty",
        "truncated": False,
    }

    obj, repairs, error = loads_lenient(raw_text or "")
    result["truncated"] = "close_truncated" in repairs
    payload = obj if isinstance(obj, dict) else None

    if payload is None and isinstance(obj, list):
        payload = {"questions": obj}

    if payload is not None:
        result["repairs"] = repairs
        result["subject"] = str(payload.get("subject") or "").strip()
        raw_questions = payload.get("questions")
        if not isinstance(raw_questions, list):
            raw_questions = []
        result["parse_mode"] = "full" if raw_questions else "empty"
    else:
        # 整体解不出来（多半是最后一题被截断），逐题恢复
        items, dropped = iter_question_objects(raw_text or "")
        if not items:
            result["parse_mode"] = "failed"
            result["error"] = error or "无法解析"
            return result
        result["repairs"] = repairs + ["per_item_recovery"]
        result["dropped"] = dropped
        result["parse_mode"] = "per_item"
        raw_questions = items

    accepted: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_questions):
        normalized, issues = normalize_question(item)
        if normalized is None:
            result["dropped"] += 1
            result["issues"][len(accepted)] = issues
            continue
        if issues:
            result["issues"][len(accepted)] = issues
        accepted.append(normalized)

    result["questions"] = accepted
    if not accepted and result["parse_mode"] == "full":
        result["parse_mode"] = "empty"
    return result
