# -*- coding: utf-8 -*-
"""
路由层接线 + 模型配置越权隔离的测试。

这层之前完全没有测试，而这次改造恰恰把三条入口的内部实现整个换掉了：
"Agent 写好了但路由还在走旧实现"是本项目上一轮返工的直接原因，所以这里用
真 FastAPI 栈打真请求，验证：

  * 三条入口确实调到 QuestionImportAgent，并按文本/视觉分流
  * 输入超限、伪装扩展名、科目不存在分别落到 400/404，而不是 500
  * 领域异常集中翻译成对用户有意义的状态码
  * 模型配置读写按 user_id 收敛，别人的 id 读不到也删不掉
  * 响应不再下发明文 api_key

数据库用内存 SQLite + 真实 ORM 模型，跑的是真的 filter/order_by/update 语义，
只在 SQLite 上把 BigInteger 主键渲染成 INTEGER 以便自增。
"""
import io
import json
import os
import sys
import unittest
from typing import Any, Dict, List

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(type_, compiler, **kw):    # noqa: ANN001
    """SQLite 只有 INTEGER 主键才自增；测试里不改生产模型定义。"""
    return "INTEGER"


from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from agents.question_import_agent import ImportOutcome
from database.db import Base, get_default_db
from database.models import LLMModel, Subject
from routers import import_router, model_router
from services.document_renderer import PageImage
from services.import_limits import InputRejected, MAX_TEXT_CHARS
from services.llm_config_service import (NoModelConfigured, VisionRequired,
                                         get_user_llm, list_models)


def _outcome(count: int) -> ImportOutcome:
    return ImportOutcome(
        subject="数学",
        questions=[{"type": "single", "question": f"第{i}题",
                    "options": ["A. 甲", "B. 乙"], "answer": "A",
                    "analysis": "依据"} for i in range(1, count + 1)],
        batches=max(1, count),
    )


def _tiny_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return buffer.getvalue()


class StubAgent:
    """记录调用、返回固定结果；路由测试只关心接线，不关心解析细节。"""

    def __init__(self, outcome: ImportOutcome = None):
        self.text_calls: List[Any] = []
        self.image_calls: List[Any] = []
        self.outcome = outcome or _outcome(2)

    def import_text(self, text, subject):
        self.text_calls.append((text, subject))
        return self.outcome

    def import_images(self, data_urls, subject):
        self.image_calls.append((data_urls, subject))
        return self.outcome


class RouteTestBase(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool)
        Base.metadata.create_all(
            self.engine, tables=[Subject.__table__, LLMModel.__table__])
        self.db = sessionmaker(bind=self.engine)()

        self.db.add_all([
            Subject(id=1, user_id=1, name="数学"),
            Subject(id=2, user_id=2, name="语文"),
            LLMModel(id=10, user_id=1, model_name="text-only",
                     base_url="http://127.0.0.1:11434/v1",
                     api_key="sk-textkey-0001", is_default=True,
                     supports_vision=False, supports_json_mode=True,
                     max_output_tokens=4096),
            LLMModel(id=11, user_id=1, model_name="vision-model",
                     base_url="http://127.0.0.1:8000/v1",
                     api_key="sk-visionkey-0002", is_default=False,
                     supports_vision=True, supports_json_mode=True,
                     max_output_tokens=8192),
            LLMModel(id=20, user_id=2, model_name="other-user",
                     base_url="https://api.example.com/v1",
                     api_key="sk-otherkey-0003", is_default=True,
                     supports_vision=False, supports_json_mode=True,
                     max_output_tokens=8192),
        ])
        self.db.commit()

        app = FastAPI()
        app.include_router(import_router.router)
        app.include_router(model_router.router)
        app.dependency_overrides[get_default_db] = lambda: self.db
        self.client = TestClient(app)

        # 模型调用一律替换成桩，测试不产生任何真实请求与费用。
        self.stub = StubAgent()
        self._real_agent = import_router._agent
        import_router._agent = lambda db, user_id, model_id, need_vision: self.stub
        self._real_render = import_router.render_to_images
        import_router.render_to_images = lambda path, **kw: [
            PageImage(1, b"\x89PNG", "image/png", 595, 842),
            PageImage(2, b"\x89PNG", "image/png", 595, 842),
        ]
        self.removed: List[str] = []
        self._real_remove = import_router._remove_temp
        import_router._remove_temp = lambda path: (
            self.removed.append(path), self._real_remove(path))

    def tearDown(self):
        import_router._agent = self._real_agent
        import_router.render_to_images = self._real_render
        import_router._remove_temp = self._real_remove
        self.db.close()
        self.engine.dispose()

    def _upload(self, url: str, filename: str, data: bytes,
                field: str = "file", extra: Dict[str, Any] = None):
        form = {"user_id": "1", "subject_id": "1"}
        form.update(extra or {})
        return self.client.post(url,
                                files={field: (filename, io.BytesIO(data),
                                               "application/octet-stream")},
                                data=form)


class TestPreviewRouting(RouteTestBase):

    def test_text_preview_reaches_agent_and_carries_stats(self):
        resp = self.client.post("/api/import/preview/text", json={
            "user_id": 1, "subject_id": 1,
            "text": "1. 甲题\nA. 一\nB. 二\n答案：A"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(self.stub.text_calls), 1)
        self.assertEqual(self.stub.image_calls, [])
        self.assertEqual(len(body["data"]["questions"]), 2)
        for key in ("batches", "dropped", "missing", "truncated", "repairs",
                    "errors"):
            self.assertIn(key, body["data"]["stats"])

    def test_subject_name_reaches_the_agent(self):
        self.client.post("/api/import/preview/text", json={
            "user_id": 1, "subject_id": 1, "text": "1. 题"})
        self.assertEqual(self.stub.text_calls[0][1], "数学")

    def test_oversized_text_is_400_with_split_hint(self):
        resp = self.client.post("/api/import/preview/text", json={
            "user_id": 1, "subject_id": 1, "text": "字" * (MAX_TEXT_CHARS + 1)})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(str(MAX_TEXT_CHARS), resp.json()["detail"])
        self.assertIn("分次", resp.json()["detail"])

    def test_unknown_subject_is_404_not_500(self):
        resp = self.client.post("/api/import/preview/text", json={
            "user_id": 1, "subject_id": 999, "text": "1. 题"})
        self.assertEqual(resp.status_code, 404)

    def test_other_users_subject_is_404(self):
        resp = self.client.post("/api/import/preview/text", json={
            "user_id": 1, "subject_id": 2, "text": "1. 题"})
        self.assertEqual(resp.status_code, 404)

    def test_txt_file_goes_through_text_channel(self):
        resp = self._upload("/api/import/preview/file", "notes.txt",
                            "1. 题干\nA. 甲\nB. 乙\n答案：A".encode("utf-8"))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(self.stub.text_calls), 1)
        self.assertEqual(self.stub.image_calls, [])

    def test_oversized_txt_file_is_rejected_too(self):
        """txt 只按字节限过不了：10MB 纯文本会切成上千个批次慢慢烧钱。"""
        resp = self._upload("/api/import/preview/file", "big.txt",
                            ("1. 题干内容\n" * 20000).encode("utf-8"))
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(self.stub.text_calls, [])

    def test_pdf_goes_through_page_rendering(self):
        resp = self._upload("/api/import/preview/file", "paper.pdf", b"%PDF-1.7 fake")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self.stub.text_calls, [])
        self.assertEqual(len(self.stub.image_calls), 1)
        self.assertEqual(len(self.stub.image_calls[0][0]), 2, "两页要送两张图")

    def test_disguised_pdf_is_rejected(self):
        resp = self._upload("/api/import/preview/file", "paper.pdf", b"PK\x03\x04zip")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PDF", resp.json()["detail"])
        self.assertEqual(self.stub.image_calls, [])

    def test_unsupported_extension_is_rejected(self):
        resp = self._upload("/api/import/preview/file", "sheet.xls", b"x" * 10)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("PDF", resp.json()["detail"])

    def test_oversized_file_is_rejected(self):
        resp = self._upload("/api/import/preview/file", "big.pdf",
                            b"%PDF" + b"a" * (10 * 1024 * 1024 + 1))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("MB", resp.json()["detail"])

    def test_temp_file_cleaned_up_after_preview(self):
        self._upload("/api/import/preview/file", "paper.pdf", b"%PDF-1.7 fake")
        self.assertTrue(self.removed, "预览完必须回收临时文件")
        for path in self.removed:
            self.assertFalse(os.path.exists(path), f"临时文件残留：{path}")

    def test_temp_file_cleaned_up_even_when_preview_fails(self):
        self._upload("/api/import/preview/file", "paper.pdf", b"not a pdf")
        self.assertTrue(self.removed)
        for path in self.removed:
            self.assertFalse(os.path.exists(path))

    def test_image_preview_sends_one_image_batch(self):
        resp = self.client.post(
            "/api/import/preview/image",
            files={"image": ("a.png", io.BytesIO(_tiny_png()), "image/png")},
            data={"user_id": "1", "subject_id": "1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(self.stub.image_calls), 1)
        self.assertEqual(self.stub.text_calls, [])

    def test_image_preview_rejects_non_image_bytes(self):
        resp = self.client.post(
            "/api/import/preview/image",
            files={"image": ("a.png", io.BytesIO(b"just text"), "image/png")},
            data={"user_id": "1", "subject_id": "1"})
        self.assertEqual(resp.status_code, 400)


class TestErrorMapping(RouteTestBase):
    """领域异常 → 状态码的映射集中在一个地方判，不散在三个 handler 里各写一套。"""

    def test_each_domain_error_maps_to_its_own_status(self):
        cases = [
            (InputRejected("超限"), 400),
            (import_router.RendererUnavailable("缺 LibreOffice"), 503),
            (import_router.LLMUnavailable("401"), 502),
            (ValueError("内容不像试卷"), 400),
        ]
        for exc, expected in cases:
            def raise_it(exc=exc):
                raise exc
            with self.assertRaises(HTTPException) as ctx:
                import_router._guard(raise_it)
            self.assertEqual(ctx.exception.status_code, expected, str(exc))

    def test_payload_message_names_missing_and_dropped(self):
        outcome = ImportOutcome(subject="数学", questions=[{"question": "1"}],
                                missing=3, dropped=1, truncated=True)
        message = import_router._payload(outcome)["message"]
        self.assertIn("成功解析 1 道题目", message)
        self.assertIn("3 道题模型没有吐回来", message)
        self.assertIn("1 道题未能解析", message)
        self.assertIn("截断", message)

    def test_payload_never_calls_zero_questions_a_success(self):
        """真机实测：0 题时 message 仍写「成功解析 0 道题目」，用户以为链路通了。"""
        outcome = ImportOutcome(subject="数学", questions=[],
                                errors=["page1 输出预算被思考占满，没有返回任何内容"])
        payload = import_router._payload(outcome)
        self.assertFalse(payload["message"].startswith("成功"), payload["message"])
        self.assertIn("没有返回任何内容", payload["message"],
                      "要把失败原因带到 message 里，不能只藏在 stats 里")

    def test_payload_partial_success_says_partial(self):
        outcome = ImportOutcome(subject="数学", questions=[{"question": "1"}],
                                errors=["batch2 送 8 题只回来 0 题"], missing=7)
        message = import_router._payload(outcome)["message"]
        self.assertIn("部分失败", message)
        self.assertIn("batch2", message)

    def test_limits_endpoint_exposes_thresholds(self):
        resp = self.client.get("/api/import/limits")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["limits"]["max_text_chars"], MAX_TEXT_CHARS)
        self.assertIn("pymupdf", data["renderer"])


class TestVisionGate(RouteTestBase):

    def test_image_preview_without_vision_config_is_rejected(self):
        """只有文本模型时不能把图片塞给它——这正是图片导入乱输出的来源之一。"""
        import_router._agent = self._real_agent
        resp = self.client.post(
            "/api/import/preview/image",
            files={"image": ("a.png", io.BytesIO(_tiny_png()), "image/png")},
            data={"user_id": "2", "subject_id": "2"})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("图片", resp.json()["detail"])

    def test_document_preview_without_vision_config_is_rejected(self):
        """user 2 只有一条纯文本配置，pdf 分支必须先拦住而不是硬送。"""
        import_router._agent = self._real_agent
        resp = self._upload("/api/import/preview/file", "paper.pdf", b"%PDF-1.7 fake",
                            extra={"user_id": "2", "subject_id": "2"})
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertIn("图片", resp.json()["detail"])

    def test_vision_capable_config_is_auto_picked(self):
        self.assertTrue(get_user_llm(self.db, 1, need_vision=True).supports_vision)

    def test_no_vision_config_raises_vision_required(self):
        with self.assertRaises(VisionRequired):
            get_user_llm(self.db, 2, need_vision=True)


class TestModelConfigIsolation(RouteTestBase):

    def test_list_returns_masked_key_only(self):
        resp = self.client.get("/api/models/", params={"user_id": 1})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()
        self.assertEqual(len(rows), 2)
        dumped = json.dumps(rows, ensure_ascii=False)
        self.assertNotIn("sk-textkey-0001", dumped)
        self.assertNotIn("sk-visionkey-0002", dumped)
        self.assertTrue(rows[0]["is_default"], "默认项要排在最前")

    def test_cannot_read_another_users_config(self):
        self.assertEqual(
            self.client.get("/api/models/20", params={"user_id": 1}).status_code, 404)

    def test_cannot_delete_another_users_config(self):
        self.assertEqual(
            self.client.delete("/api/models/20", params={"user_id": 1}).status_code,
            404)
        self.assertEqual(
            self.db.query(LLMModel).filter(LLMModel.id == 20).first().user_id, 2,
            "越权删除不能真的动数据")

    def test_update_of_foreign_config_returns_404(self):
        resp = self.client.put("/api/models/20", json={
            "user_id": 1, "model_name": "hijack",
            "base_url": "https://api.example.com/v1", "api_key": "sk-x"})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(
            self.db.query(LLMModel).filter(LLMModel.id == 20).first().model_name,
            "other-user")

    def test_make_foreign_config_default_is_not_a_500(self):
        resp = self.client.post("/api/models/20/default", params={"user_id": 1})
        self.assertIn(resp.status_code, (400, 404),
                      f"越权设为默认应返回客户端错误：{resp.status_code} {resp.text}")

    def test_first_config_becomes_default_and_key_is_masked(self):
        resp = self.client.post("/api/models/", json={
            "user_id": 7, "model_name": "first",
            "base_url": "http://127.0.0.1:11434/v1", "api_key": "sk-abcdef123456"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["is_default"])
        self.assertNotIn("sk-abcdef123456", json.dumps(body))
        self.assertEqual(body["api_key_masked"], "sk-******3456")

    def test_local_model_endpoint_is_allowed(self):
        resp = self.client.post("/api/models/", json={
            "user_id": 8, "model_name": "ollama",
            "base_url": "http://localhost:11434/v1", "api_key": "sk-local"})
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_cloud_metadata_endpoint_is_blocked(self):
        resp = self.client.post("/api/models/", json={
            "user_id": 9, "model_name": "evil",
            "base_url": "http://169.254.169.254/latest/meta-data", "api_key": "k"})
        self.assertEqual(resp.status_code, 400)

    def test_update_without_api_key_keeps_existing_secret(self):
        resp = self.client.put("/api/models/10", json={
            "user_id": 1, "model_name": "renamed",
            "base_url": "http://127.0.0.1:11434/v1",
            "supports_vision": False, "supports_json_mode": True,
            "max_output_tokens": 8192})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(
            self.db.query(LLMModel).filter(LLMModel.id == 10).first().api_key,
            "sk-textkey-0001")

    def test_default_selection_prefers_flag_then_id(self):
        self.assertEqual([r.id for r in list_models(self.db, 1)], [10, 11])
        self.assertEqual(get_user_llm(self.db, 1).id, 10)

    def test_foreign_model_id_cannot_be_used_for_import(self):
        with self.assertRaises(NoModelConfigured):
            get_user_llm(self.db, 1, model_id=20)

    def test_deleting_default_promotes_another_one(self):
        resp = self.client.delete("/api/models/10", params={"user_id": 1})
        self.assertEqual(resp.status_code, 200, resp.text)
        remaining = list_models(self.db, 1)
        self.assertEqual(len(remaining), 1)
        self.assertTrue(remaining[0].is_default, "删掉默认项后必须有人顶上")


if __name__ == "__main__":
    unittest.main(verbosity=2)
