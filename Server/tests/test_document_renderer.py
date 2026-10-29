# -*- coding: utf-8 -*-
"""
文档整页渲染契约的测试（TDD 先行）。

决策依据（2026-10-29 实测 测试用的材料/文档/）：
  docx 里的公式是 OLE 对象（数学卷 179 个、化学 116、物理 95），
  python-docx 的 paragraph.text 读到 0 个；改用 pandoc 3.12.1 转 markdown，
  公式仍然全部落成 ![](media/imageNN.wmf) 图片引用（数学 187 个、物理 124、
  化学 156），0 个变成可计算的 LaTeX 文本。
  → 本地文本提取在结构上就拿不到公式，继续提取只会给模型喂残句。

因此文件导入不再做任何本地文本提取：本地只把文档逐页转成图片，
把整页视觉内容原样交给支持视觉的大模型判断。本模块只负责"渲染成图"。
"""
import os
import sys
import tempfile
import unittest

SERVER_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_ROOT not in sys.path:
    sys.path.insert(0, SERVER_ROOT)

import fitz  # PyMuPDF

from services import document_renderer
from services.import_limits import InputRejected


def _make_pdf(page_count: int, width: int = 595, height: int = 842) -> str:
    """生成一份纯文字 PDF 作为渲染夹具。"""
    path = os.path.join(tempfile.mkdtemp(prefix="render_"), "paper.pdf")
    doc = fitz.open()
    for i in range(page_count):
        page = doc.new_page(width=width, height=height)
        page.insert_text((72, 100), f"Page {i + 1} question stem", fontsize=14)
    doc.save(path)
    doc.close()
    return path


class TestCapabilities(unittest.TestCase):

    def test_reports_both_backends(self):
        caps = document_renderer.capabilities()
        self.assertIn("pymupdf", caps)
        self.assertIn("soffice", caps)
        self.assertIsInstance(caps["pymupdf"], bool)
        self.assertIsInstance(caps["soffice"], bool)

    def test_pymupdf_present_in_this_environment(self):
        # PDF 渲染只依赖 pip 包，服务器装不上系统组件时这条也必须能过
        self.assertTrue(document_renderer.capabilities()["pymupdf"])


class TestRenderPdf(unittest.TestCase):

    def setUp(self):
        self.path = _make_pdf(3)

    def test_returns_one_image_per_page(self):
        pages = document_renderer.render_to_images(self.path)
        self.assertEqual(len(pages), 3)
        self.assertEqual([p.page_no for p in pages], [1, 2, 3])

    def test_pages_are_png_and_non_empty(self):
        for page in document_renderer.render_to_images(self.path):
            self.assertEqual(page.mime, "image/png")
            self.assertTrue(page.data.startswith(b"\x89PNG"))
            self.assertGreater(len(page.data), 500)

    def test_images_are_not_text(self):
        """本模块的边界：只出图，绝不在本地做文本提取。"""
        page = document_renderer.render_to_images(self.path)[0]
        self.assertFalse(hasattr(page, "text"))

    def test_higher_dpi_yields_more_pixels(self):
        low = document_renderer.render_to_images(self.path, dpi=72)[0]
        high = document_renderer.render_to_images(self.path, dpi=144)[0]
        self.assertGreater(high.width, low.width)
        self.assertAlmostEqual(high.width / low.width, 2.0, delta=0.1)

    def test_reports_page_dimensions(self):
        page = document_renderer.render_to_images(self.path, dpi=72)[0]
        self.assertEqual((page.width, page.height), (595, 842))

    def test_page_limit_rejected_before_rendering(self):
        with self.assertRaises(InputRejected) as ctx:
            document_renderer.render_to_images(self.path, max_pages=2)
        self.assertIn("3", str(ctx.exception))
        self.assertIn("分", str(ctx.exception))

    def test_each_page_fits_vision_budget(self):
        for page in document_renderer.render_to_images(self.path):
            self.assertLessEqual(len(page.data), document_renderer.MAX_PAGE_IMAGE_BYTES)


class TestRenderWord(unittest.TestCase):

    def setUp(self):
        self.path = os.path.join(
            os.path.dirname(SERVER_ROOT), "测试用的材料", "文档",
            "2026年高考数学试卷（全国2卷）.docx")

    def test_docx_without_soffice_raises_actionable_error(self):
        if not os.path.exists(self.path):
            self.skipTest("缺少 Word 试卷样本")
        original = document_renderer.capabilities
        document_renderer.capabilities = lambda: {"pymupdf": True, "soffice": False}
        try:
            with self.assertRaises(document_renderer.RendererUnavailable) as ctx:
                document_renderer.render_to_images(self.path)
        finally:
            document_renderer.capabilities = original
        self.assertIn("LibreOffice", str(ctx.exception))

    def test_docx_with_soffice_returns_pages(self):
        if not os.path.exists(self.path):
            self.skipTest("缺少 Word 试卷样本")
        if not document_renderer.capabilities()["soffice"]:
            self.skipTest("本机未安装 LibreOffice，无法验证 docx 渲染路径")
        pages = document_renderer.render_to_images(self.path)
        self.assertGreaterEqual(len(pages), 1)

    def test_real_word_paper_renders_every_page(self):
        """真实试卷的页数必须被完整覆盖，不允许只渲染首页。"""
        if not os.path.exists(self.path):
            self.skipTest("缺少 Word 试卷样本")
        if not document_renderer.capabilities()["soffice"]:
            self.skipTest("本机未安装 LibreOffice")
        pages = document_renderer.render_to_images(self.path)
        self.assertEqual(pages[-1].page_no, len(pages))


class TestUnsupportedInput(unittest.TestCase):

    def test_rejects_unknown_extension(self):
        path = os.path.join(tempfile.mkdtemp(), "x.rtf")
        with open(path, "wb") as fh:
            fh.write(b"{\\rtf1}")
        with self.assertRaises(InputRejected):
            document_renderer.render_to_images(path)

    def test_rejects_missing_file(self):
        with self.assertRaises(InputRejected):
            document_renderer.render_to_images(os.path.join(tempfile.gettempdir(),
                                                            "definitely-absent.pdf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
