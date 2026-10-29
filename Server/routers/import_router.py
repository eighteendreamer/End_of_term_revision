"""
题目导入路由（文件 / 图片 / 文本 → 大模型识别 → 预览 → 入库）

三条入口共用 agents.question_import_agent 一套流程；本层只做四件事：
校验输入限制、挑模型配置、把领域异常翻译成对用户有意义的状态码、返回统计。

调用模型的处理端点一律声明为同步 def，交给 Starlette 线程池执行。
原先 async def 里直接调阻塞的模型请求，会在单进程 uvicorn 下把整个事件循环
卡住几十秒到几分钟，连带 /health 与聊天 WebSocket 一起无响应。
"""
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agents.question_import_agent import QuestionImportAgent
from database.db import get_default_db
from database.models import Subject
from services import import_limits
from services.document_renderer import RendererUnavailable, render_to_images
from services.llm_client import LLMUnavailable
from services.llm_config_service import (NoModelConfigured, VisionRequired,
                                         build_client, get_user_llm)
from services.question_service import QuestionService

router = APIRouter(prefix="/api/import", tags=["题目导入"])

TEXT_EXTENSIONS = {".txt"}


class TextImportRequest(BaseModel):
    """文本导入请求"""
    user_id: int
    subject_id: int
    text: str
    model_id: Optional[int] = None


class ConfirmImportRequest(BaseModel):
    """确认导入请求"""
    user_id: int
    subject_id: int
    questions: List[Dict[str, Any]]


# ----------------------------------------------------------------------
# 辅助
# ----------------------------------------------------------------------

def _load_subject(db: Session, user_id: int, subject_id: int) -> Subject:
    subject = (db.query(Subject)
               .filter(Subject.id == subject_id, Subject.user_id == user_id)
               .first())
    if not subject:
        raise HTTPException(status_code=404, detail="科目不存在或无权访问")
    return subject


def _agent(db: Session, user_id: int, model_id: Optional[int],
           need_vision: bool) -> QuestionImportAgent:
    try:
        config = get_user_llm(db, user_id, model_id=model_id,
                              need_vision=need_vision)
    except (NoModelConfigured, VisionRequired) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return QuestionImportAgent(build_client(config))


def _save_temp(upload_file: UploadFile) -> str:
    """把上传流落到临时文件，返回路径。"""
    suffix = os.path.splitext(upload_file.filename or "")[1].lower()
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        handle.write(upload_file.file.read())
    finally:
        handle.close()
    return handle.name


def _read(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def _remove_temp(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _data_url(data: bytes) -> str:
    import base64
    mime = import_limits.detect_mime(data)
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _payload(outcome) -> Dict[str, Any]:
    data = outcome.as_dict()
    stats = data["stats"]
    count = len(data["questions"])
    if count == 0:
        # 一批都没回来时不能报"成功解析 0 道题目"：用户会以为链路通了
        reason = stats["errors"][0] if stats["errors"] else "模型没有返回任何题目"
        message = f"导入失败：{reason}"
        return {"code": 200, "message": message, "data": data}

    message = f"成功解析 {count} 道题目"
    if stats["missing"]:
        message += f"，{stats['missing']} 道题模型没有吐回来"
    if stats["dropped"]:
        message += f"，{stats['dropped']} 道题未能解析"
    if stats["truncated"]:
        message += "；部分批次输出被截断，建议缩小单次导入范围"
    if stats["errors"]:
        message += f"；部分失败：{stats['errors'][0]}"
    return {"code": 200, "message": message, "data": data}


def _guard(call):
    """统一把领域异常映射成状态码，保留可操作的提示文案。"""
    try:
        return call()
    except import_limits.InputRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RendererUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ----------------------------------------------------------------------
# 预览（第一步：识别，不写库）
# ----------------------------------------------------------------------

@router.post("/preview/text")
def preview_from_text(request: TextImportRequest,
                      db: Session = Depends(get_default_db)):
    """文本导入预览。"""
    subject = _load_subject(db, request.user_id, request.subject_id)
    agent = _agent(db, request.user_id, request.model_id, need_vision=False)

    def work():
        import_limits.check_text(request.text, field="文本")
        return agent.import_text(request.text, subject.name)

    return _payload(_guard(work))


@router.post("/preview/image")
def preview_from_image(user_id: int = Form(...),
                       subject_id: int = Form(...),
                       model_id: Optional[int] = Form(None),
                       image: UploadFile = File(...),
                       db: Session = Depends(get_default_db)):
    """图片导入预览：整张图交给支持视觉的模型。"""
    subject = _load_subject(db, user_id, subject_id)
    agent = _agent(db, user_id, model_id, need_vision=True)
    path = _save_temp(image)

    def work():
        prepared = import_limits.check_image(_read(path))
        return agent.import_images([_data_url(prepared)], subject.name)

    try:
        return _payload(_guard(work))
    finally:
        _remove_temp(path)


@router.post("/preview/file")
def preview_from_file(user_id: int = Form(...),
                      subject_id: int = Form(...),
                      model_id: Optional[int] = Form(None),
                      file: UploadFile = File(...),
                      db: Session = Depends(get_default_db)):
    """
    文件导入预览。

    .txt 走文本通道；.pdf/.docx/.doc 整页渲染成图片后走视觉通道。
    这里刻意不做本地文本提取——理科卷的公式在 docx 里是 OLE 对象，
    实测 python-docx 读到 0 个、pandoc 也只给出 .wmf 图片引用，
    本地提取必然丢公式，把残句交给模型只会得到幻觉。
    """
    subject = _load_subject(db, user_id, subject_id)
    path = _save_temp(file)

    def work():
        data = _read(path)
        ext = import_limits.check_document(file.filename, data)
        if ext in TEXT_EXTENSIONS:
            agent = _agent(db, user_id, model_id, need_vision=False)
            # 字节数过不了 10MB 不代表字符数过得了上限：10MB 纯文本会被切成
            # 上千个批次慢慢跑完，必须按字符数拦下来让用户拆分。
            text = import_limits.check_text(import_limits.decode_text(data),
                                            field="文件")
            return agent.import_text(text, subject.name)

        agent = _agent(db, user_id, model_id, need_vision=True)
        pages = render_to_images(path)
        return agent.import_images([page.data_url() for page in pages],
                                   subject.name)

    try:
        return _payload(_guard(work))
    finally:
        _remove_temp(path)


# ----------------------------------------------------------------------
# 确认入库（第二步）
# ----------------------------------------------------------------------

@router.post("/confirm")
def confirm_import(request: ConfirmImportRequest,
                   db: Session = Depends(get_default_db)):
    """确认导入：把预览得到的题目写入库，含去重与题目资源。"""
    _load_subject(db, request.user_id, request.subject_id)
    if not request.questions:
        raise HTTPException(status_code=400, detail="没有可导入的题目")

    try:
        result = QuestionService.batch_create_questions(
            db=db,
            user_id=request.user_id,
            subject_id=request.subject_id,
            questions_data=request.questions,
            skip_duplicates=True,
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500,
                            detail=f"保存失败：{type(exc).__name__}") from exc

    message = f"成功导入 {result['created_count']} 道题目"
    if result["skipped_count"]:
        message += f"（跳过 {result['skipped_count']} 道重复题目）"
    return {
        "code": 200,
        "message": message,
        "data": {
            "created_count": result["created_count"],
            "skipped_count": result["skipped_count"],
            "total_input": result["total_input"],
        },
    }


# ----------------------------------------------------------------------
# 诊断
# ----------------------------------------------------------------------

@router.get("/limits")
def import_limits_snapshot():
    """当前生效的输入限制与渲染能力，供前端提示与运维核对。"""
    from services.document_renderer import capabilities
    return {
        "code": 200,
        "data": {
            "limits": import_limits.summarize_limits(),
            "renderer": capabilities(),
        },
    }
