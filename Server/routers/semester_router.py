"""
学期管理路由
按 user_id 完全隔离，支持增删改查及标记当前学期
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database.db import get_default_db
from database.models import Semester

router = APIRouter(prefix="/api/semesters", tags=["semesters"])


# ==================== Schema ====================

class SemesterCreate(BaseModel):
    user_id: int
    name: str
    start_date: Optional[str] = None   # ISO 日期字符串 "2025-09-01"
    end_date: Optional[str] = None
    is_current: Optional[bool] = False


class SemesterUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None


# ==================== 工具 ====================

def _parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"日期格式错误: {s}，请用 ISO 8601 格式")


def _to_dict(sem: Semester) -> dict:
    return {
        "id": sem.id,
        "user_id": sem.user_id,
        "name": sem.name,
        "start_date": sem.start_date.isoformat() if sem.start_date else None,
        "end_date": sem.end_date.isoformat() if sem.end_date else None,
        "is_current": bool(sem.is_current),
        "created_at": sem.created_at.isoformat() if sem.created_at else None,
        "updated_at": sem.updated_at.isoformat() if sem.updated_at else None,
    }


def _set_current(user_id: int, semester_id: int, db: Session):
    """将指定学期设为当前，其余清零"""
    db.query(Semester).filter(
        Semester.user_id == user_id,
        Semester.id != semester_id
    ).update({"is_current": 0})
    db.query(Semester).filter(
        Semester.user_id == user_id,
        Semester.id == semester_id
    ).update({"is_current": 1})


# ==================== 接口 ====================

@router.get("")
def list_semesters(user_id: int, db: Session = Depends(get_default_db)):
    """获取该用户所有学期（按开始日期降序，最新在前）"""
    sems = (
        db.query(Semester)
        .filter(Semester.user_id == user_id)
        .order_by(
            Semester.start_date.is_(None).asc(),   # NULL 排最后（MySQL 兼容写法）
            Semester.start_date.desc(),
            Semester.created_at.desc()
        )
        .all()
    )
    return {"code": 200, "message": "获取成功", "data": [_to_dict(s) for s in sems]}


@router.get("/current")
def get_current_semester(user_id: int, db: Session = Depends(get_default_db)):
    """获取当前学期（is_current=1），没有则返回 null"""
    sem = db.query(Semester).filter(
        Semester.user_id == user_id,
        Semester.is_current == 1
    ).first()
    return {"code": 200, "message": "获取成功", "data": _to_dict(sem) if sem else None}


@router.post("")
def create_semester(body: SemesterCreate, db: Session = Depends(get_default_db)):
    """创建学期"""
    sem = Semester(
        user_id=body.user_id,
        name=body.name.strip(),
        start_date=_parse_date(body.start_date),
        end_date=_parse_date(body.end_date),
        is_current=1 if body.is_current else 0,
    )
    db.add(sem)
    db.flush()  # 拿到 id

    # 若设为当前，清除其他学期的 is_current
    if body.is_current:
        _set_current(body.user_id, sem.id, db)

    db.commit()
    db.refresh(sem)
    return {"code": 200, "message": "创建成功", "data": _to_dict(sem)}


@router.put("/{sem_id}")
def update_semester(
    sem_id: int,
    body: SemesterUpdate,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """更新学期"""
    sem = db.query(Semester).filter(
        Semester.id == sem_id,
        Semester.user_id == user_id
    ).first()
    if not sem:
        raise HTTPException(status_code=404, detail="学期不存在或无权操作")

    if body.name is not None:
        sem.name = body.name.strip()
    if body.start_date is not None:
        sem.start_date = _parse_date(body.start_date)
    if body.end_date is not None:
        sem.end_date = _parse_date(body.end_date)
    if body.is_current is not None:
        if body.is_current:
            _set_current(user_id, sem_id, db)
        else:
            sem.is_current = 0

    db.commit()
    db.refresh(sem)
    return {"code": 200, "message": "更新成功", "data": _to_dict(sem)}


@router.patch("/{sem_id}/set-current")
def set_current_semester(
    sem_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """将指定学期设为当前学期"""
    sem = db.query(Semester).filter(
        Semester.id == sem_id,
        Semester.user_id == user_id
    ).first()
    if not sem:
        raise HTTPException(status_code=404, detail="学期不存在或无权操作")
    _set_current(user_id, sem_id, db)
    db.commit()
    db.refresh(sem)
    return {"code": 200, "message": "已设为当前学期", "data": _to_dict(sem)}


@router.delete("/{sem_id}")
def delete_semester(
    sem_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """删除学期（科目/考试的 semester_id 会被 SET NULL）"""
    sem = db.query(Semester).filter(
        Semester.id == sem_id,
        Semester.user_id == user_id
    ).first()
    if not sem:
        raise HTTPException(status_code=404, detail="学期不存在或无权操作")
    db.delete(sem)
    db.commit()
    return {"code": 200, "message": "删除成功"}
