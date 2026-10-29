# -*- coding: utf-8 -*-
"""
文档整页渲染。

本模块刻意不做任何本地文本提取。原因（2026-10-29 实测，见
tests/test_document_renderer.py 顶部说明）：理科试卷的公式在 docx 里是 OLE
对象，python-docx 读到 0 个，pandoc 也只是把它们落成 .wmf 图片引用——本地
提取在结构上就拿不到公式，喂给模型只会得到残句并诱发幻觉。

所以文件导入的分工是：本地只把文档逐页变成图片，视觉内容由模型自己读。
  .pdf        → PyMuPDF 直接逐页渲染（纯 pip 依赖，服务器无需装系统组件）
  .docx/.doc  → 先由 LibreOffice 转 PDF，再逐页渲染
缺依赖时报可执行的错误，不回落到有损的文本提取。
"""
import base64
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Optional

from services.import_limits import InputRejected, MAX_PDF_PAGES

RENDER_DPI = 170
MAX_PAGE_IMAGE_BYTES = 1_500_000
RENDERABLE_EXT = {".pdf", ".docx", ".doc"}
TEXT_ONLY_EXT = {".txt"}
_SOFFICE_NAMES = ("soffice", "libreoffice")
_SOFFICE_TIMEOUT = 120

_PDF_HEADER = b"%PDF"


class RendererUnavailable(Exception):
    """服务器缺少渲染所需的外部组件。message 面向运维，含安装指引。"""


@dataclass
class PageImage:
    """一页文档的视觉快照。"""
    page_no: int
    data: bytes
    mime: str
    width: int
    height: int

    def data_url(self) -> str:
        encoded = base64.b64encode(self.data).decode("ascii")
        return f"data:{self.mime};base64,{encoded}"


_fitz_cache: Dict[str, object] = {}
_soffice_cache: Dict[str, Optional[str]] = {}


def capabilities() -> Dict[str, bool]:
    """报告两个渲染后端的可用性，供路由与前端展示。"""
    return {"pymupdf": _load_fitz() is not None, "soffice": _find_soffice() is not None}


def render_to_images(path: str, *, dpi: int = RENDER_DPI,
                     max_pages: int = MAX_PDF_PAGES) -> List[PageImage]:
    """
    把文档逐页渲染成 PNG。

    :raises InputRejected: 扩展名不支持、文件缺失或页数超限
    :raises RendererUnavailable: 服务器缺少 PyMuPDF 或 LibreOffice
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_ONLY_EXT:
        raise InputRejected("纯文本没有版面信息，请改用文本导入")
    if ext not in RENDERABLE_EXT:
        raise InputRejected(f"不支持 {ext or '该'} 格式，请上传 PDF 或 Word(.docx/.doc)")
    if not os.path.exists(path):
        raise InputRejected("文件不存在或已被清理，请重新上传")

    fitz = _load_fitz()
    if fitz is None:
        raise RendererUnavailable(
            "服务器缺少 PyMuPDF，无法把文档渲染成图片。"
            "请在后端环境执行 python -m pip install PyMuPDF")

    pdf_path = path if ext == ".pdf" else _to_pdf(path, ext)
    return _rasterize(fitz, pdf_path, dpi, max_pages)


def _to_pdf(path: str, ext: str) -> str:
    """Word → PDF。这一步只换容器，不读取任何文字内容。"""
    soffice = capabilities()["soffice"] and _find_soffice()
    if not soffice:
        raise RendererUnavailable(
            f"服务器缺少 LibreOffice，无法把 {ext} 转成可识别的版面图片。"
            "请在服务器安装：apt-get install -y libreoffice（或确认 soffice 在 PATH 中）。"
            "若只需导入纯文字，请改用文本导入。")

    outdir = tempfile.mkdtemp(prefix="doc_render_")
    try:
        result = subprocess.run(
            [soffice, "--headless", "--norestore", "--convert-to", "pdf",
             "--outdir", outdir, path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=_SOFFICE_TIMEOUT, check=False,
        )
        pdf_path = os.path.join(
            outdir, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        if not os.path.exists(pdf_path):
            detail = (result.stderr or result.stdout or b"").decode("utf-8", "ignore")
            raise RendererUnavailable(
                f"LibreOffice 转换失败，文档可能已损坏或被加密。{detail[:200]}")
        return pdf_path
    except subprocess.TimeoutExpired:
        raise RendererUnavailable(
            f"LibreOffice 转换超过 {_SOFFICE_TIMEOUT} 秒，文档可能过大，请拆分后重试")
    finally:
        _rmtree(outdir)


def _rasterize(fitz, pdf_path: str, dpi: int, max_pages: int) -> List[PageImage]:
    doc = fitz.open(pdf_path)
    try:
        total = doc.page_count
        if total == 0:
            raise InputRejected("文档没有任何页面")
        if total > max_pages:
            raise InputRejected(
                f"文档共 {total} 页，超过单次最多 {max_pages} 页的上限，"
                f"请按页或按大题分次导入")

        pages: List[PageImage] = []
        for index in range(total):
            pages.append(_render_page(fitz, doc, index, dpi))
        return pages
    finally:
        doc.close()


def _render_page(fitz, doc, index: int, dpi: int) -> PageImage:
    """先按目标 DPI 出 PNG；单页过大时降 DPI 并退化为 JPEG，保证能上送模型。"""
    page = doc.load_page(index)
    for candidate_dpi in (dpi, 120, 90):
        pix = page.get_pixmap(dpi=candidate_dpi)
        data = pix.tobytes("png")
        if len(data) <= MAX_PAGE_IMAGE_BYTES:
            return PageImage(page_no=index + 1, data=data, mime="image/png",
                             width=pix.width, height=pix.height)

    pix = page.get_pixmap(dpi=90)
    return PageImage(page_no=index + 1, data=pix.tobytes("jpeg"), mime="image/jpeg",
                     width=pix.width, height=pix.height)


def _load_fitz():
    if "fitz" in _fitz_cache:
        return _fitz_cache["fitz"]
    module = None
    try:
        import pymupdf as module  # PyMuPDF 2.x 起的正式名
    except ImportError:
        try:
            import fitz as module  # 1.x 兼容
        except ImportError:
            module = None
    _fitz_cache["fitz"] = module
    return module


def _find_soffice() -> Optional[str]:
    if "path" in _soffice_cache:
        return _soffice_cache["path"]
    from shutil import which
    _soffice_cache["path"] = next((n for n in _SOFFICE_NAMES if which(n)), None)
    return _soffice_cache["path"]


def _rmtree(path: str) -> None:
    import shutil
    shutil.rmtree(path, ignore_errors=True)
