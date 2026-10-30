# -*- coding: utf-8 -*-
"""
输出上限的配置来源与它推导出的批大小。

2026-10-29 实测：用户可用的两家 OpenAI 兼容网关（apihub.agnes-ai.com、
api.layso.ai）的 /models 都只返回 id/created/owned_by/supported_endpoint_types，
不报自己的输出上限，所以"向端点探测能力"这条路走不通，按用户决定统一配 128k；
实测它们接受 max_tokens 到 131072。这个值只是天花板：每批实际发送量由题数算出来，
它真正影响的是"一批塞几题"和"被截断后能加码到多少"。
"""
import os
import sys
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from services import llm_config_service
from services.llm_client import (BATCH_SIZE_CEILING, BATCH_SIZE_FLOOR, LLMClient,
                                 PER_QUESTION_OUTPUT_TOKENS)


def _client(ceiling):
    return LLMClient("https://x/v1", "k", "m", max_output_tokens=ceiling)


class DynamicBatchSize(unittest.TestCase):
    """一批塞几题由模型上限推导，不写死 8。"""

    def test_small_ceiling_shrinks_the_batch(self):
        self.assertEqual(_client(2048).questions_per_batch, BATCH_SIZE_FLOOR)

    def test_batch_scales_with_the_ceiling(self):
        size = _client(8192).questions_per_batch
        self.assertEqual(size, 8192 // PER_QUESTION_OUTPUT_TOKENS)
        self.assertGreater(size, 8, "上限够大就该少发几批，直接减轻限流压力")

    def test_big_ceiling_is_still_capped(self):
        """批太大一旦截断要拆更多次，收益抵不过风险，所以留天花板。"""
        self.assertEqual(_client(200000).questions_per_batch, BATCH_SIZE_CEILING)

    def test_budget_for_a_full_batch_fits_the_ceiling(self):
        client = _client(200000)
        self.assertLessEqual(client.output_budget(client.questions_per_batch),
                             client.max_output_tokens)


class ConfiguredDefault(unittest.TestCase):
    """默认值要真的撑得起"一批 16 题 + 截断后还能加码"，否则等于白填。"""

    def test_default_allows_a_full_batch_and_one_doubling(self):
        client = _client(llm_config_service.DEFAULT_MAX_OUTPUT_TOKENS)
        full = client.output_budget(client.questions_per_batch)
        self.assertEqual(client.questions_per_batch, BATCH_SIZE_CEILING)
        self.assertGreaterEqual(client.budget_for_retry(full), full * 2,
                                "被截断后至少要还能加码一倍")

    def test_default_stays_inside_the_editable_range(self):
        self.assertLessEqual(llm_config_service.DEFAULT_MAX_OUTPUT_TOKENS,
                             llm_config_service.MAX_OUTPUT_TOKENS_BOUND)
        self.assertGreaterEqual(llm_config_service.DEFAULT_MAX_OUTPUT_TOKENS,
                                llm_config_service.MIN_OUTPUT_TOKENS)


class LiteralSingleSource(unittest.TestCase):
    """默认值与取值范围只能有一处定义，其余地方引用它。"""

    def _read(self, *parts):
        with open(os.path.join(SERVER_ROOT, *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_router_has_no_hardcoded_numbers(self):
        source = self._read("routers", "model_router.py")
        self.assertNotIn("default=8192", source)
        self.assertNotIn("default=128000", source)
        self.assertNotIn("ge=256", source)
        self.assertNotIn("le=200000", source)
        self.assertIn("DEFAULT_MAX_OUTPUT_TOKENS", source)

    def test_probe_is_gone(self):
        """网关不报能力，探测代码就是死路径，不该留着。"""
        self.assertNotIn("probe_max_output_tokens",
                         self._read("routers", "model_router.py"))
        self.assertNotIn("def probe_max_output_tokens",
                         self._read("services", "llm_config_service.py"))

    def test_frontend_form_has_no_hardcoded_default(self):
        path = os.path.join(os.path.dirname(SERVER_ROOT),
                            "fronted", "src", "views", "ModelConfig.vue")
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("max_output_tokens: 8192", source)
        self.assertIn("modelApi.defaults", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
