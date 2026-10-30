# -*- coding: utf-8 -*-
"""
模型输出上限的来源与动态批大小。

2026-10-29 实测用户网关（apihub.agnes-ai.com）：GET /models 只返回
id/created/owned_by/supported_endpoint_types，没有任何输出上限字段；
且 /models/{不存在的名字} 用 HTTP 200 返回 error 体。
所以"自动拿最大输出 tokens"只能做成：端点肯给就用端点的，不给就沿用手填值并
如实标出来——绝不替用户猜一个数，猜大了会 400，猜小了会静默截断。
"""
import json
import os
import sys
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from services import llm_config_service
from services.llm_client import (BATCH_SIZE_CEILING, BATCH_SIZE_FLOOR, LLMClient,
                                 PER_QUESTION_OUTPUT_TOKENS)


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class ProbeTest(unittest.TestCase):
    """探测函数：只认端点真的说了话，其余一律 None。"""

    def _patch(self, responses):
        calls = []

        def fake_get(url, headers=None, **kwargs):
            calls.append(url)
            outcome = responses[min(len(calls) - 1, len(responses) - 1)]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        original = llm_config_service._http_get
        llm_config_service._http_get = fake_get
        self.addCleanup(setattr, llm_config_service, "_http_get", original)
        return calls

    def test_reads_max_output_tokens_from_single_model_endpoint(self):
        self._patch([FakeResponse(payload={"id": "m", "max_output_tokens": 65536})])
        self.assertEqual(
            llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m"), 65536)

    def test_falls_back_to_model_list(self):
        self._patch([
            FakeResponse(status=404),
            FakeResponse(payload={"data": [
                {"id": "other"},
                {"id": "m", "limits": {"output": 32768}}]}),
        ])
        self.assertEqual(
            llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m"), 32768)

    def test_http200_error_body_is_not_a_capability(self):
        """实测该网关用 200 返回 error，不能当成"这个模型上限是 0"。"""
        self._patch([
            FakeResponse(payload={"error": {"code": "model_not_found"}}),
            FakeResponse(payload={"error": {"code": "model_not_found"}}),
        ])
        self.assertIsNone(
            llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m"))

    def test_silent_gateway_like_ours_returns_none(self):
        self._patch([
            FakeResponse(payload={"id": "m", "object": "model"}),
            FakeResponse(payload={"data": [{"id": "m", "owned_by": "custom",
                                            "created": 1,
                                            "supported_endpoint_types": ["openai"]}]}),
        ])
        self.assertIsNone(
            llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m"),
            "端点没说的字段不能凭空造")

    def test_network_error_never_raises(self):
        self._patch([OSError("connection reset")])
        self.assertIsNone(
            llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m"))

    def test_absurd_value_is_clamped_to_the_editable_range(self):
        self._patch([FakeResponse(payload={"max_output_tokens": 999_999_999})])
        got = llm_config_service.probe_max_output_tokens("https://x/v1", "k", "m")
        self.assertEqual(got, llm_config_service.MAX_OUTPUT_TOKENS_BOUND)


class DynamicBatchSize(unittest.TestCase):
    """一批塞几题由模型自己的输出上限决定，不是写死的 8。"""

    def _client(self, ceiling):
        return LLMClient("https://x/v1", "k", "m", max_output_tokens=ceiling)

    def test_small_ceiling_shrinks_the_batch(self):
        self.assertEqual(self._client(2048).questions_per_batch, BATCH_SIZE_FLOOR)

    def test_batch_scales_with_the_ceiling(self):
        size = self._client(8192).questions_per_batch
        self.assertEqual(size, 8192 // PER_QUESTION_OUTPUT_TOKENS)
        self.assertGreater(size, 8, "上限够大就该少发几批，直接减轻限流压力")

    def test_big_ceiling_is_still_capped(self):
        """批太大一旦截断要拆更多次，收益抵不过风险，所以留天花板。"""
        self.assertEqual(self._client(200000).questions_per_batch, BATCH_SIZE_CEILING)

    def test_output_budget_uses_the_same_per_question_estimate(self):
        client = self._client(200000)
        size = client.questions_per_batch
        self.assertLessEqual(client.output_budget(size), client.max_output_tokens,
                             "按这个批大小算出来的预算必须装得进模型自己的上限")


class LiteralSingleSource(unittest.TestCase):
    """默认值与取值范围只能有一处定义。"""

    def _read(self, rel):
        with open(os.path.join(SERVER_ROOT, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()

    def test_router_has_no_hardcoded_numbers(self):
        source = self._read("routers/model_router.py")
        self.assertNotIn("default=8192", source)
        self.assertNotIn("ge=256", source)
        self.assertNotIn("le=200000", source)
        self.assertIn("DEFAULT_MAX_OUTPUT_TOKENS", source)

    def test_frontend_form_has_no_hardcoded_default(self):
        path = os.path.join(os.path.dirname(SERVER_ROOT),
                            "fronted", "src", "views", "ModelConfig.vue")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("max_output_tokens: 8192", source)
        self.assertIn("modelApi.defaults", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
