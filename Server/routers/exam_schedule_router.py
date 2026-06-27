"""
考试日程路由（顶栏倒计时功能）
按 user_id 完全隔离，支持增删改查
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database.db import get_default_db
from database.models import ExamSchedule, Subject, Semester

router = APIRouter(prefix="/api/exam-schedules", tags=["exam-schedules"])


# ==================== Schema ====================

class ExamScheduleCreate(BaseModel):
    user_id: int
    subject_name: str
    subject_id: Optional[int] = None
    semester_id: Optional[int] = None
    exam_time: str
    exam_location: Optional[str] = None
    note: Optional[str] = None


class ExamScheduleUpdate(BaseModel):
    subject_name: Optional[str] = None
    subject_id: Optional[int] = None
    semester_id: Optional[int] = None
    exam_time: Optional[str] = None
    exam_location: Optional[str] = None
    note: Optional[str] = None


# ==================== 工具 ====================

def _to_dict(exam: ExamSchedule) -> dict:
    return {
        "id": exam.id,
        "user_id": exam.user_id,
        "subject_name": exam.subject_name,
        "subject_id": exam.subject_id,
        "semester_id": exam.semester_id,
        "exam_time": exam.exam_time.isoformat() if exam.exam_time else None,
        "exam_location": exam.exam_location,
        "note": exam.note,
        "created_at": exam.created_at.isoformat() if exam.created_at else None,
        "updated_at": exam.updated_at.isoformat() if exam.updated_at else None,
    }


# ==================== 接口 ====================

@router.get("")
def list_exams(user_id: int, semester_id: Optional[int] = None, db: Session = Depends(get_default_db)):
    """获取该用户的所有考试日程（按考试时间升序），可按学期筛选"""
    q = db.query(ExamSchedule).filter(ExamSchedule.user_id == user_id)
    if semester_id is not None:
        q = q.filter(ExamSchedule.semester_id == semester_id)
    exams = q.order_by(ExamSchedule.exam_time.asc()).all()
    return {"code": 200, "message": "获取成功", "data": [_to_dict(e) for e in exams]}


@router.get("/upcoming")
def get_upcoming_exam(user_id: int, semester_id: Optional[int] = None, db: Session = Depends(get_default_db)):
    """下一门考试（顶栏倒计时专用），可按学期筛选"""
    now = datetime.now()
    q = db.query(ExamSchedule).filter(
        ExamSchedule.user_id == user_id,
        ExamSchedule.exam_time > now
    )
    if semester_id is not None:
        q = q.filter(ExamSchedule.semester_id == semester_id)
    exam = q.order_by(ExamSchedule.exam_time.asc()).first()
    return {"code": 200, "message": "获取成功", "data": _to_dict(exam) if exam else None}


@router.post("")
def create_exam(body: ExamScheduleCreate, db: Session = Depends(get_default_db)):
    """创建考试日程"""
    try:
        exam_time = datetime.fromisoformat(body.exam_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="考试时间格式错误，请使用 ISO 8601 格式")

    # 如果传了 subject_id，校验是否属于该用户
    if body.subject_id:
        subj = db.query(Subject).filter(
            Subject.id == body.subject_id,
            Subject.user_id == body.user_id
        ).first()
        if not subj:
            body.subject_id = None  # 静默忽略不合法的 subject_id

    exam = ExamSchedule(
        user_id=body.user_id,
        subject_name=body.subject_name.strip(),
        subject_id=body.subject_id,
        semester_id=body.semester_id,
        exam_time=exam_time,
        exam_location=body.exam_location,
        note=body.note,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return {"code": 200, "message": "创建成功", "data": _to_dict(exam)}


@router.put("/{exam_id}")
def update_exam(
    exam_id: int,
    body: ExamScheduleUpdate,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """更新考试日程（只允许本人操作）"""
    exam = db.query(ExamSchedule).filter(
        ExamSchedule.id == exam_id,
        ExamSchedule.user_id == user_id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试日程不存在或无权操作")

    if body.subject_name is not None:
        exam.subject_name = body.subject_name.strip()
    if body.subject_id is not None:
        exam.subject_id = body.subject_id
    if body.semester_id is not None:
        exam.semester_id = body.semester_id
    if body.exam_time is not None:
        try:
            exam.exam_time = datetime.fromisoformat(body.exam_time)
        except ValueError:
            raise HTTPException(status_code=400, detail="考试时间格式错误")
    if body.exam_location is not None:
        exam.exam_location = body.exam_location
    if body.note is not None:
        exam.note = body.note

    db.commit()
    db.refresh(exam)
    return {"code": 200, "message": "更新成功", "data": _to_dict(exam)}


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """删除考试日程（只允许本人操作）"""
    exam = db.query(ExamSchedule).filter(
        ExamSchedule.id == exam_id,
        ExamSchedule.user_id == user_id
    ).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试日程不存在或无权操作")

    db.delete(exam)
    db.commit()
    return {"code": 200, "message": "删除成功"}
