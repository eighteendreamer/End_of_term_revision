"""
题目路由
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database.db import get_default_db
from database.models import Question
from services.question_service import QuestionService
from services.share_service import ShareService  # 新增
from utils.cache_manager import invalidate_question_related_cache
from utils.redis_client import redis_client
import json

router = APIRouter(prefix="/api/questions", tags=["题目管理"])


class QuestionResponse(BaseModel):
    """题目响应"""
    id: int
    subject_id: int
    user_id: int
    type: str
    question: str
    options: List[str]
    answer: str
    analysis: str
    created_at: str
    can_edit: bool = False  # 是否可编辑（删除）


class QuestionCreate(BaseModel):
    """创建题目请求"""
    user_id: int
    subject_id: int
    type: str
    question: str
    options: List[str]
    answer: str
    analysis: str


@router.post("/", response_model=QuestionResponse)
def create_question(question: QuestionCreate, db: Session = Depends(get_default_db)):
    """创建单个题目"""
    db_question = QuestionService.create_question(
        db=db,
        user_id=question.user_id,
        subject_id=question.subject_id,
        question_type=question.type,
        question=question.question,
        options=question.options,
        answer=question.answer,
        analysis=question.analysis
    )
    db.commit()
    db.refresh(db_question)
    invalidate_question_related_cache(question.user_id, question.subject_id)
    
    return _format_question_response(db_question, question.user_id, db)


@router.get("/", response_model=List[QuestionResponse])
def get_questions(
    user_id: int,
    subject_id: Optional[int] = None,
    question_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_default_db)
):
    """获取题目列表（支持分页，默认每页20条）
    - subject_id 可选，不传则查询该用户所有题目
    """
    cache_key = (
        f"questions:user:{user_id}:list:subject:{subject_id or 'all'}:"
        f"type:{question_type or 'all'}:page:{page}:size:{page_size}"
    )
    cached_data = redis_client.get(cache_key)
    if cached_data is not None:
        return [QuestionResponse(**item) for item in cached_data]

    questions = QuestionService.get_questions_by_subject(
        db=db,
        user_id=user_id,
        subject_id=subject_id,
        question_type=question_type,
        page=page,
        page_size=page_size
    )
    
    result = [_format_question_response(q, user_id, db).dict() for q in questions]
    redis_client.set(cache_key, result, expire=300)
    return [QuestionResponse(**item) for item in result]


@router.get("/types/{subject_id}")
def get_question_types(
    subject_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """获取科目下的所有题目类型"""
    cache_key = f"questions:user:{user_id}:types:subject:{subject_id}"
    cached_data = redis_client.get(cache_key)
    if cached_data is not None:
        return cached_data

    types = QuestionService.get_question_types_by_subject(db, user_id, subject_id)
    result = {"types": types}
    redis_client.set(cache_key, result, expire=300)
    return result


@router.get("/statistics/{subject_id}")
def get_question_statistics(
    subject_id: int,
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """获取科目下的题目数量统计（查询所有题目）"""
    cache_key = f"questions:user:{user_id}:statistics:subject:{subject_id}"
    cached_data = redis_client.get(cache_key)
    if cached_data is not None:
        return cached_data

    statistics = QuestionService.get_question_statistics(db, user_id, subject_id)
    redis_client.set(cache_key, statistics, expire=300)
    return statistics


@router.get("/statistics")
def get_all_question_statistics(
    user_id: int,
    db: Session = Depends(get_default_db)
):
    """获取用户所有题目的数量统计"""
    cache_key = f"questions:user:{user_id}:statistics:subject:all"
    cached_data = redis_client.get(cache_key)
    if cached_data is not None:
        return cached_data

    statistics = QuestionService.get_question_statistics(db, user_id, subject_id=None)
    redis_client.set(cache_key, statistics, expire=300)
    return statistics


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(question_id: int, user_id: int, db: Session = Depends(get_default_db)):
    """获取单个题目"""
    question = QuestionService.get_question_by_id(db, question_id)
    
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    # 检查访问权限
    if not ShareService.can_access_subject(user_id, question.subject_id, db):
        raise HTTPException(status_code=403, detail="无权访问此题目")
    
    return _format_question_response(question, user_id, db)


@router.delete("/{question_id}")
def delete_question(question_id: int, user_id: int, db: Session = Depends(get_default_db)):
    """删除题目（仅科目拥有者可删除）"""
    # 获取题目
    question = QuestionService.get_question_by_id(db, question_id, user_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    
    # 权限检查：只有科目拥有者可删除题目
    if not ShareService.can_edit_subject(user_id, question.subject_id, db):
        raise HTTPException(status_code=403, detail="无权删除此题目")
    
    success = QuestionService.delete_question(db, question_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="删除失败")
    
    invalidate_question_related_cache(user_id, question.subject_id)
    return {"message": "题目删除成功"}


def _format_question_response(question: Question, user_id: int, db: Session) -> QuestionResponse:
    """格式化题目响应"""
    options = []
    if question.options_json:
        try:
            options = json.loads(question.options_json)
        except:
            options = []
    
    # 检查是否有编辑权限（只有科目拥有者可以编辑/删除）
    can_edit = ShareService.can_edit_subject(user_id, question.subject_id, db)
    
    return QuestionResponse(
        id=question.id,
        subject_id=question.subject_id,
        user_id=question.user_id,
        type=question.type.value,
        question=question.question,
        options=options,
        answer=question.answer,
        analysis=question.analysis,
        created_at=question.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        can_edit=can_edit
    )
