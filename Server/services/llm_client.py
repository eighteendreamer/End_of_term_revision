# -*- coding: utf-8 -*-
"""
统一 LLM 客户端：OpenAI 兼容协议直连，输出预算与截断检测全部在代码侧掌握。

刻意不用 LangChain 包装：本模块需要精确拿到 finish_reason、按批次设定
max_tokens、并在网关不支持 response_format 时降级，这些都被包装层挡住。
"""
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_RETRIES = 2
RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

# 中文约 1 字 0.6~1 token，英文约 4 字符 1 token；取保守值再留 15% 余量
_TOKEN_SAFETY = 1.15


def estimate_tokens(text: str) -> int:
    """无需依赖 tokenizer 的保守估算，用于分块装箱。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if _is_cjk(ch))
    other = len(text) - cjk
    return int((cjk * 1.0 + other / 3.0) * _TOKEN_SAFETY) + 1


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (0x3400 <= code <= 0x9FFF or 0xF900 <= code <= 0xFAFF
            or 0x3040 <= code <= 0x30FF or 0xFF00 <= code <= 0xFF60)


@dataclass
class LLMResult:
    text: str
    finish_reason: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    json_mode_used: bool = False
    attempts: int = 0
    truncated: bool = False
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.text)


class LLMUnavailable(Exception):
    """模型侧不可用（鉴权、网络、持续 5xx）。message 面向用户。"""


class LLMClient:
    """一个实例绑定一份模型配置；调用方负责按用户取配置。"""

    def __init__(self, base_url: str, api_key: str, model_name: str,
                 *, temperature: float = 0.2,
                 supports_json_mode: bool = True,
                 max_output_tokens: int = 8192,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_retries: int = DEFAULT_MAX_RETRIES):
        self.model_name = model_name
        self.temperature = temperature
        self.supports_json_mode = supports_json_mode
        self.max_output_tokens = max_output_tokens
        self.max_retries = max_retries
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout,
                              max_retries=0)

    def output_budget(self, question_count: int, per_question: int = 700) -> int:
        """按本批题量算输出预算，并夹在模型自身上限内。"""
        wanted = max(1024, question_count * per_question + 256)
        return int(min(wanted, self.max_output_tokens))

    def complete_json(self, system: str, user: str, max_tokens: int,
                      images: Optional[List[str]] = None) -> LLMResult:
        """
        要求模型返回 JSON。images 为 data URI 列表，非空时走多模态消息。

        response_format 不被支持时自动摘掉重试，并把该能力标记为不可用，
        后续同一实例不再重复试错。
        """
        messages = self._build_messages(system, user, images)
        errors: List[str] = []
        attempts = 0

        for attempt in range(self.max_retries + 1):
            attempts += 1
            use_json_mode = self.supports_json_mode
            kwargs: Dict[str, Any] = {
                "model": self.model_name,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": max_tokens,
            }
            if use_json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            try:
                response = self._client.chat.completions.create(**kwargs)
            except APIStatusError as exc:
                status = exc.status_code
                if use_json_mode and status in (400, 404, 422):
                    self.supports_json_mode = False
                    errors.append(f"response_format 被拒({status})，已降级")
                    attempts -= 1
                elif status in RETRYABLE_STATUS and attempt < self.max_retries:
                    errors.append(f"HTTP {status}")
                    self._backoff(attempt)
                else:
                    errors.append(f"HTTP {status}")
                    raise LLMUnavailable(self._friendly(status, exc)) from exc
                continue
            except (APITimeoutError, APIConnectionError) as exc:
                errors.append(f"{type(exc).__name__}")
                if attempt >= self.max_retries:
                    raise LLMUnavailable("模型服务连接失败或超时，请稍后重试") from exc
                self._backoff(attempt)
                continue

            return self._to_result(response, use_json_mode, attempts, errors)

        raise LLMUnavailable("模型调用失败：" + "；".join(errors[-2:]))

    def _build_messages(self, system: str, user: str,
                        images: Optional[List[str]]) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
        if not images:
            messages.append({"role": "user", "content": user})
            return messages

        content: List[Dict[str, Any]] = [
            {"type": "image_url", "image_url": {"url": url}} for url in images
        ]
        content.append({"type": "text", "text": user})
        messages.append({"role": "user", "content": content})
        return messages

    def _to_result(self, response: Any, json_mode: bool, attempts: int,
                   errors: List[str]) -> LLMResult:
        choice = response.choices[0] if response.choices else None
        text = (choice.message.content or "") if choice else ""
        reason = getattr(choice, "finish_reason", None) or "unknown"

        usage = getattr(response, "usage", None)
        return LLMResult(
            text=text,
            finish_reason=reason,
            model=getattr(response, "model", self.model_name) or self.model_name,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            json_mode_used=json_mode,
            attempts=attempts,
            truncated=reason == "length",
            errors=list(errors),
        )

    def _friendly(self, status: int, exc: APIStatusError) -> str:
        if status in (401, 403):
            return "模型鉴权失败，请检查 AI 模型配置里的 api-key 与 base_url"
        if status == 404:
            return "模型地址或模型名不存在，请检查 AI 模型配置里的 name 与 url"
        if status == 429:
            return "模型请求过于频繁（限流），请稍后重试"
        return f"模型服务返回 HTTP {status}"

    @staticmethod
    def _backoff(attempt: int) -> None:
        time.sleep(min(8.0, (2 ** attempt) + random.random()))
