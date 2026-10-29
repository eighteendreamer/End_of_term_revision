# -*- coding: utf-8 -*-
"""
导入输入侧的硬限制与校验。

阈值集中在这里，路由和 agent 不再各自写数字。
数值依据 2026-10-29 对 测试用的材料/ 的真实测量：
  docx 提取后 1.4k~22k 字符；OLE 公式对象 95~179 个，预览图为 WMF；
  截图 561x1039 上下、54~160KB。
"""
import io
import os
from typing import Dict, List, Optional, Tuple

from PIL import Image

MAX_FILE_BYTES = 10 * 1024 * 1024          # 上传文件 10MB
MAX_PDF_PAGES = 30                          # 单次最多 30 页
MAX_IMAGE_BYTES = 6 * 1024 * 1024           # 图片原始 6MB
MAX_TEXT_CHARS = 60_000                     # 提取后/粘贴的纯文本上限
MAX_IMAGE_EDGE = 2048                       # 图片长边
MAX_IMAGE_PIXELS = 40_000_000               # 防解压炸弹
TARGET_IMAGE_BYTES = 3 * 1024 * 1024        # 压完目标体积
JPEG_QUALITY_STEPS = (85, 75, 65, 55)

ALLOWED_DOC_EXT = {".pdf", ".docx", ".doc", ".txt"}
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_PIL_TO_EXT = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp", "BMP": ".bmp", "GIF": ".gif"}

# OLE Compound File 头：老式 .doc 与 Equation 3.0 对象的共同特征
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class InputRejected(Exception):
    """输入不符合限制。message 直接面向用户。"""


def check_text(text: str, *, field: str = "文本") -> str:
    if not text or not text.strip():
        raise InputRejected(f"{field}内容为空")
    if len(text) > MAX_TEXT_CHARS:
        raise InputRejected(
            f"{field}共 {len(text)} 字符，超过单次上限 {MAX_TEXT_CHARS}。"
            f"请按章节或大题分次导入。"
        )
    return text


def check_document(filename: str, data: bytes) -> str:
    """校验文档类型与体积，返回规范化扩展名。"""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_DOC_EXT:
        raise InputRejected(
            f"不支持 {ext or '该'} 格式。请上传 PDF、Word(.docx) 或文本(.txt)。"
            f"老版 .doc 请先另存为 .docx。"
        )
    if len(data) > MAX_FILE_BYTES:
        raise InputRejected(f"文件 {len(data) // 1024}KB，超过 {MAX_FILE_BYTES // 1024 // 1024}MB 上限")
    if not data.strip():
        raise InputRejected("文件内容为空")

    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise InputRejected("文件头不是 PDF，请确认文件未损坏")
    elif ext == ".docx":
        if data.startswith(_OLE_MAGIC):
            raise InputRejected("这是老式 .doc 二进制文档，请把扩展名改为 .doc 或另存为 .docx")
        if not data.startswith(b"PK\x03\x04"):
            raise InputRejected("该 .docx 不是有效的 Office Open XML，文件可能已损坏")
    elif ext == ".doc":
        if data.startswith(b"PK\x03\x04"):
            raise InputRejected("内容是 .docx 格式但扩展名是 .doc，请改回 .docx")
        if not data.startswith(_OLE_MAGIC):
            raise InputRejected("该 .doc 不是有效的 Word 97-2003 文档，文件可能已损坏")
    return ext


def check_image(data: bytes) -> bytes:
    """
    校验图片真实格式并压缩到长边上限，返回可直接 base64 上送的字节。

    不信任文件名和 Content-Type：扩展名是 .png 也可能塞任意字节。
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise InputRejected(f"图片 {len(data) // 1024}KB，超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB 上限")

    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            fmt = (im.format or "").upper()
            width, height = im.size
    except Exception:
        raise InputRejected("无法识别的图片内容，请确认文件未损坏且为 JPG/PNG/WebP 等常见格式")

    if width * height > MAX_IMAGE_PIXELS:
        raise InputRejected(f"图片像素 {width}x{height} 过大，请先裁剪或降低分辨率")

    if max(width, height) <= MAX_IMAGE_EDGE and len(data) <= TARGET_IMAGE_BYTES \
            and fmt in _PIL_TO_EXT and fmt != "GIF":
        return data

    return _downscale(im, fmt)


def _downscale(im: Image.Image, fmt: str) -> bytes:
    image = im.convert("RGB")
    width, height = image.size
    scale = MAX_IMAGE_EDGE / max(width, height)
    if scale < 1:
        image = image.resize(
            (max(1, int(width * scale)), max(1, int(height * scale))),
            Image.LANCZOS,
        )

    for quality in JPEG_QUALITY_STEPS:
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= TARGET_IMAGE_BYTES:
            return buf.getvalue()
    return buf.getvalue()


def rasterize_wmf(blob: bytes) -> Tuple[Optional[bytes], str]:
    """
    把 docx 里的 WMF 公式预览图转成 PNG。

    :return: (PNG 字节 或 None, 状态说明)
    """
    try:
        with Image.open(io.BytesIO(blob)) as im:
            im.load()
            buf = io.BytesIO()
            im.convert("RGB").save(buf, format="PNG")
            return buf.getvalue(), "ok"
    except Exception as exc:
        return None, f"Pillow 无法解码 WMF: {type(exc).__name__}"


def detect_mime(data: bytes) -> str:
    """按文件头判断真实图片格式，不信任扩展名与上传声明。"""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data.startswith(b"BM"):
        return "image/bmp"
    return "application/octet-stream"


def decode_text(data: bytes) -> str:
    """中文 .txt 常见 UTF-8 与 GBK 两种编码，逐个试，全失败才报错。"""
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise InputRejected("文本文件编码无法识别，请另存为 UTF-8 或 GBK 后重试")


def summarize_limits() -> Dict[str, object]:
    """给前端 / 健康检查用的当前生效阈值。"""
    return {
        "max_file_bytes": MAX_FILE_BYTES,
        "max_pdf_pages": MAX_PDF_PAGES,
        "max_text_chars": MAX_TEXT_CHARS,
        "max_image_bytes": MAX_IMAGE_BYTES,
        "max_image_edge": MAX_IMAGE_EDGE,
        "allowed_doc_ext": sorted(ALLOWED_DOC_EXT),
        "allowed_image_ext": sorted(ALLOWED_IMAGE_EXT),
    }
