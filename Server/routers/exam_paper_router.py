"""
试卷练习 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from database.db import get_default_db
from services.exam_paper_service import ExamPaperService

router = APIRouter(prefix="/api/exam-papers", tags=["exam-papers"])


# ============================================================
# 请求/响应模型
# ============================================================

class CreatePaperRequest(BaseModel):
    """创建试卷请求"""
    user_id: int
    subject_id: int
    paper_type: str  # 'normal' or 'error'
    title: str
    duration: Optional[int] = None  # 分钟数，None表示不限时
    question_counts: Dict[str, int]  # {single: 10, multiple: 5, ...}


class SaveAnswerRequest(BaseModel):
    """保存答案请求"""
    user_id: int
    question_id: int
    user_answer: str
    images: List[str] = []


class SubmitPaperRequest(BaseModel):
    """提交试卷请求"""
    user_id: int
    answers: List[Dict[str, Any]]  # [{question_id, user_answer, images}, ...]


# ============================================================
# API 路由
# ============================================================

@router.post("")
async def create_paper(request: CreatePaperRequest, db: Session = Depends(get_default_db)):
    """
    创建试卷
    """
    try:
        result = ExamPaperService.create_paper(
            db=db,
            user_id=request.user_id,
            subject_id=request.subject_id,
            paper_type=request.paper_type,
            title=request.title,
            duration=request.duration,
            question_counts=request.question_counts
        )
        return {"code": 200, "message": "创建成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建试卷失败: {str(e)}")


@router.get("")
async def get_papers(
    user_id: int,
    paper_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_default_db)
):
    """
    获取试卷列表
    """
    try:
        papers = ExamPaperService.get_papers(
            db=db,
            user_id=user_id,
            paper_type=paper_type,
            status=status
        )
        return {"code": 200, "message": "获取成功", "data": {"papers": papers}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取试卷列表失败: {str(e)}")


@router.get("/{paper_id}")
async def get_paper_detail(
    paper_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """
    获取试卷详情
    """
    try:
        detail = ExamPaperService.get_paper_detail(
            db=db,
            paper_id=paper_id,
            user_id=user_id
        )
        return {"code": 200, "message": "获取成功", "data": detail}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取试卷详情失败: {str(e)}")


@router.post("/{paper_id}/save-answer")
async def save_answer(
    paper_id: int,
    request: SaveAnswerRequest,
    db: Session = Depends(get_default_db)
):
    """
    保存答案（自动保存）
    """
    try:
        result = ExamPaperService.save_answer(
            db=db,
            paper_id=paper_id,
            user_id=request.user_id,
            question_id=request.question_id,
            user_answer=request.user_answer,
            images=request.images
        )
        return {"code": 200, "message": "保存成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存答案失败: {str(e)}")


@router.post("/{paper_id}/submit")
async def submit_paper(
    paper_id: int,
    request: SubmitPaperRequest,
    db: Session = Depends(get_default_db)
):
    """
    提交试卷
    """
    try:
        result = ExamPaperService.submit_paper(
            db=db,
            paper_id=paper_id,
            user_id=request.user_id,
            answers=request.answers
        )
        return {"code": 200, "message": "提交成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交试卷失败: {str(e)}")
