# -*- coding: utf-8 -*-
"""
LLM 客户端的两条真机取证结论对应的契约。

2026-10-29 用 agnes-2.5-flash 跑三档梯度时实测到：
  1) 思考型模型会把整批 max_tokens 花在隐藏思考上，返回 finish_reason=length
     且 content 为空字符串。此时对用户说"未解析出任何题目"是没有处置方向的废话，
     必须区分"输出被截断（还有半截 JSON 可救）"与"一个字都没返回（预算不够）"。
  2) 网关限流窗口比 3 次退避（≈12s）长，7 个批次里有 3 个直接死于 429。
     429 与 5xx 的重试预算不该一样。
"""
import os
import sys
import time
import unittest

import httpx
import openai

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from services.llm_client import LLMClient, LLMUnavailable


def _response(content: str, finish_reason: str):
    class Message:
        def __init__(self):
            self.content = content

    class Choice:
        def __init__(self):
            self.message = Message()
            self.finish_reason = finish_reason

    class Usage:
        prompt_tokens = 11
        completion_tokens = 22

    class Resp:
        def __init__(self):
            self.choices = [Choice()]
            self.model = "fake-reasoning"
            self.usage = Usage()

    return Resp()


def _status_error(status: int):
    request = httpx.Request("POST", "https://fake.test/v1/chat/completions")
    response = httpx.Response(status, request=request)
    return openai.RateLimitError("boom", response=response, body=None)


class ClientStub(LLMClient):
    """替掉 OpenAI SDK 传输层，只记录调用节奏。"""

    def __init__(self, outcomes, **kwargs):
        super().__init__("https://fake.test/v1", "k", "fake-reasoning",
                         max_output_tokens=kwargs.pop("max_output_tokens", 8192),
                         **kwargs)
        self.outcomes = list(outcomes)
        self.calls = []

        def create(**kwargs):
            self.calls.append(kwargs)
            outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        completions = type("Completions", (), {"create": staticmethod(create)})()
        chat = type("Chat", (), {"completions": completions})()
        self._client = type("Client", (), {"chat": chat})()


class TestStarvedOutput(unittest.TestCase):
    """finish_reason=length 且 content 为空 = 预算被思考吃光，不是普通截断。"""

    def test_empty_content_with_length_reason_is_starved(self):
        client = ClientStub([_response("", "length")])
        result = client.complete_json("sys", "user", 4000)
        self.assertTrue(result.truncated)
        self.assertTrue(result.starved, "空返回必须能被单独识别出来")

    def test_partial_json_is_truncated_but_not_starved(self):
        client = ClientStub([_response('{"questions": [{"type":', "length")])
        result = client.complete_json("sys", "user", 4000)
        self.assertTrue(result.truncated)
        self.assertFalse(result.starved)

    def test_normal_stop_is_neither(self):
        client = ClientStub([_response('{"questions": []}', "stop")])
        result = client.complete_json("sys", "user", 4000)
        self.assertFalse(result.truncated)
        self.assertFalse(result.starved)


class TestRateLimitRetry(unittest.TestCase):
    """429 要给比 5xx 更长的重试预算，否则整批题会静默消失。"""

    def test_429_then_success_recovers_within_backoff_budget(self):
        client = ClientStub([_status_error(429), _status_error(429),
                             _status_error(429), _response('{"questions": []}', "stop")])
        start = time.time()
        result = client.complete_json("sys", "user", 4000)
        self.assertTrue(result.ok)
        self.assertGreaterEqual(len(client.calls), 4, "前三次 429 必须被重试掉")
        self.assertGreater(time.time() - start, 1.0, "429 之间要有真实退避，不能打点重试")

    def test_429_gives_up_with_actionable_message(self):
        client = ClientStub([_status_error(429)] * 12)
        with self.assertRaises(LLMUnavailable) as ctx:
            client.complete_json("sys", "user", 4000)
        self.assertIn("频繁", str(ctx.exception))

    def test_429_waits_longer_than_server_error(self):
        fast = ClientStub([_status_error(503), _response('{"questions": []}', "stop")])
        slow = ClientStub([_status_error(429), _response('{"questions": []}', "stop")])
        t0 = time.time()
        fast.complete_json("sys", "user", 4000)
        quick = time.time() - t0
        t0 = time.time()
        slow.complete_json("sys", "user", 4000)
        throttled = time.time() - t0
        self.assertGreater(throttled, quick,
                           "限流是窗口问题，退避该比偶发 5xx 更久")


if __name__ == "__main__":
    unittest.main(verbosity=2)
