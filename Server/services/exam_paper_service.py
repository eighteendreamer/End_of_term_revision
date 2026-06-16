"""
试卷练习服务（基于扩展的 PracticeSession 和 PracticeRecord）
处理试卷的创建、查询、答题、提交等业务逻辑
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime, timedelta
from database.models import (
    PracticeSession, PracticeRecord, Question, Subject, User, ErrorBook
)
from services.question_service import QuestionService
from services.error_service import ErrorService
from services.paper_generation_service import PaperGenerationService
from utils.cache_manager import invalidate_practice_related_cache
import json


class ExamPaperService:
    """试卷服务类（复用 PracticeSession 和 PracticeRecord）"""
    
    @staticmethod
    def create_paper(
        db: Session,
        user_id: int,
        subject_id: int,
        paper_type: str,
        title: str,
        duration: Optional[int],
        question_counts: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        创建试卷
        :param db: 数据库会话
        :param user_id: 用户ID
        :param subject_id: 科目ID
        :param paper_type: 试卷类型 (normal/error)
        :param title: 试卷标题
        :param duration: 时长（分钟），None表示不限时
        :param question_counts: 题型数量配置 {single: 10, multiple: 5, ...}
        :return: 试卷信息和题目列表
        """
        # 1. 智能获取题目
        questions = PaperGenerationService.generate_questions(
            db=db,
            user_id=user_id,
            subject_id=subject_id,
            paper_type=paper_type,
            question_counts=question_counts
        )
        
        if not questions:
            raise ValueError("没有足够的题目创建试卷")
        
        # 2. 计算过期时间
        expires_at = None
        if duration:
            expires_at = datetime.now() + timedelta(minutes=duration)
        
        # 3. 创建试卷会话（使用 PracticeSession）
        session_type = f'paper_{paper_type}'  # 'paper_normal' or 'paper_error'
        
        session = PracticeSession(
            user_id=user_id,
            subject_id=subject_id,
            session_type=session_type,
            title=title,
            duration=duration,
            status='in_progress',
            expires_at=expires_at,
            total_count=len(questions),
            correct_count=0,
            wrong_count=0,
            accuracy='0',
            grade='未完成'
        )
        db.add(session)
        db.flush()  # 获取session.id
        
        # 4. 创建试卷题目记录（使用 PracticeRecord）
        for idx, question in enumerate(questions, start=1):
            record = PracticeRecord(
                session_id=session.id,
                user_id=user_id,
                subject_id=subject_id,
                question_id=question.id,
                question_order=idx,
                user_answer='',  # 初始为空
                is_correct=0  # 初始为0
            )
            db.add(record)
        
        db.commit()
        db.refresh(session)
        
        # 5. 返回试卷和题目列表
        return {
            "paper_id": session.id,
            "title": session.title,
            "duration": session.duration,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "questions": ExamPaperService._format_questions(questions)
        }
    
    @staticmethod
    def get_papers(
        db: Session,
        user_id: int,
        paper_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取试卷列表
        :param db: 数据库会话
        :param user_id: 用户ID
        :param paper_type: 试卷类型筛选 (normal/error)
        :param status: 状态筛选 (in_progress/completed/expired)
        :return: 试卷列表
        """
        # 只查询试卷类型的会话（排除即时练习）
        query = db.query(PracticeSession).filter(
            PracticeSession.user_id == user_id,
            PracticeSession.session_type.in_(['paper_normal', 'paper_error'])
        )
        
        if paper_type:
            session_type = f'paper_{paper_type}'
            query = query.filter(PracticeSession.session_type == session_type)
        
        if status:
            query = query.filter(PracticeSession.status == status)
        
        sessions = query.order_by(PracticeSession.created_at.desc()).all()
        
        result = []
        for session in sessions:
            # 获取科目名称
            subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
            
            # 计算已答题数
            answered_count = db.query(PracticeRecord).filter(
                PracticeRecord.session_id == session.id,
                PracticeRecord.user_answer != '',
                PracticeRecord.user_answer.isnot(None)
            ).count()
            
            # 计算进度
            progress = (answered_count / session.total_count * 100) if session.total_count > 0 else 0
            
            has_time_limit = session.duration is not None and session.duration > 0

            # 计算剩余时间（秒）
            remaining_time = 0
            if has_time_limit and session.expires_at and session.status == 'in_progress':
                remaining_seconds = (session.expires_at - datetime.now()).total_seconds()
                remaining_time = max(0, int(remaining_seconds))
            
            # 提取试卷类型
            paper_type_value = session.session_type.replace('paper_', '')  # 'paper_normal' -> 'normal'
            
            result.append({
                "id": session.id,
                "title": session.title,
                "subject_name": subject.name if subject else "未知科目",
                "paper_type": paper_type_value,
                "status": session.status,
                "total_questions": session.total_count,
                "answered_questions": answered_count,
                "progress": round(progress, 1),
                "remaining_time": remaining_time,
                "duration": session.duration,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "score": session.correct_count * 2 if session.status == 'completed' else None,  # 每题2分
                "accuracy": session.accuracy if session.status == 'completed' else None
            })
        
        return result
    
    @staticmethod
    def get_paper_detail(
        db: Session,
        paper_id: int,
        user_id: int
    ) -> Dict[str, Any]:
        """
        获取试卷详情
        :param db: 数据库会话
        :param paper_id: 试卷ID（session_id）
        :param user_id: 用户ID
        :return: 试卷详情和题目列表
        """
        # 1. 验证权限
        session = db.query(PracticeSession).filter(
            PracticeSession.id == paper_id,
            PracticeSession.user_id == user_id
        ).first()
        
        if not session:
            raise ValueError("试卷不存在或无权访问")
        
        has_time_limit = session.duration is not None and session.duration > 0

        # 2. 检查是否过期
        if has_time_limit and session.expires_at and datetime.now() > session.expires_at and session.status == 'in_progress':
            session.status = 'expired'
            db.commit()
        
        # 3. 获取科目信息
        subject = db.query(Subject).filter(Subject.id == session.subject_id).first()
        
        # 4. 计算剩余时间
        remaining_time = 0
        if has_time_limit and session.expires_at and session.status == 'in_progress':
            remaining_seconds = (session.expires_at - datetime.now()).total_seconds()
            remaining_time = max(0, int(remaining_seconds))
        
        # 5. 获取题目和答案
        records = db.query(PracticeRecord).filter(
            PracticeRecord.session_id == paper_id
        ).order_by(PracticeRecord.question_order).all()
        
        # 计算已答题数
        answered_count = sum(1 for r in records if r.user_answer and r.user_answer.strip())
        
        questions = []
        for record in records:
            question = db.query(Question).filter(Question.id == record.question_id).first()
            if question:
                questions.append({
                    "id": question.id,
                    "question": question.question,
                    "type": question.type.value,
                    "options": json.loads(question.options_json) if question.options_json else [],
                    "score": 2,  # 默认分值
                    "user_answer": record.user_answer,
                    "answer_images": json.loads(record.answer_images) if record.answer_images else [],
                    "is_correct": record.is_correct if session.status == 'completed' else None,
                    "answer": question.answer if session.status == 'completed' else None,
                    "analysis": question.analysis if session.status == 'completed' else None
                })
        
        return {
            "paper": {
                "id": session.id,
                "title": session.title,
                "subject_name": subject.name if subject else "未知科目",
                "status": session.status,
                "total_questions": session.total_count,
                "answered_questions": answered_count,
                "remaining_time": remaining_time,
                "duration": session.duration,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "score": session.correct_count * 2 if session.status == 'completed' else None,
                "accuracy": session.accuracy if session.status == 'completed' else None
            },
            "questions": questions
        }
    
    @staticmethod
    def save_answer(
        db: Session,
        paper_id: int,
        user_id: int,
        question_id: int,
        user_answer: str,
        images: List[str]
    ) -> Dict[str, Any]:
        """
        保存答案（自动保存）
        :param db: 数据库会话
        :param paper_id: 试卷ID（session_id）
        :param user_id: 用户ID
        :param question_id: 题目ID
        :param user_answer: 用户答案
        :param images: 答案图片列表
        :return: 保存结果
        """
        # 1. 验证权限
        session = db.query(PracticeSession).filter(
            PracticeSession.id == paper_id,
            PracticeSession.user_id == user_id
        ).first()
        
        if not session:
            raise ValueError("试卷不存在或无权访问")
        
        # 2. 检查试卷状态
        if session.status != 'in_progress':
            raise ValueError("试卷已完成或已过期，无法保存答案")
        
        # 3. 更新答案
        record = db.query(PracticeRecord).filter(
            PracticeRecord.session_id == paper_id,
            PracticeRecord.question_id == question_id
        ).first()
        
        if not record:
            raise ValueError("题目不存在")
        
        record.user_answer = user_answer
        record.answer_images = json.dumps(images) if images else None
        record.answered_at = datetime.now()
        
        db.commit()
        
        # 4. 计算已答题数
        answered_count = db.query(PracticeRecord).filter(
            PracticeRecord.session_id == paper_id,
            PracticeRecord.user_answer != '',
            PracticeRecord.user_answer.isnot(None)
        ).count()
        
        return {
            "success": True,
            "answered_questions": answered_count
        }
    
    @staticmethod
    def submit_paper(
        db: Session,
        paper_id: int,
        user_id: int,
        answers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        提交试卷
        :param db: 数据库会话
        :param paper_id: 试卷ID（session_id）
        :param user_id: 用户ID
        :param answers: 答案列表 [{question_id, user_answer, images}, ...]
        :return: 成绩信息
        """
        # 1. 验证权限
        session = db.query(PracticeSession).filter(
            PracticeSession.id == paper_id,
            PracticeSession.user_id == user_id
        ).first()
        
        if not session:
            raise ValueError("试卷不存在或无权访问")
        
        # 2. 检查试卷状态
        if session.status == 'completed':
            raise ValueError("试卷已提交，请勿重复提交")
        
        # 3. 保存所有答案
        for answer_data in answers:
            ExamPaperService.save_answer(
                db, paper_id, user_id,
                answer_data['question_id'],
                answer_data['user_answer'],
                answer_data.get('images', [])
            )
        
        # 4. 评分
        records = db.query(PracticeRecord).filter(
            PracticeRecord.session_id == paper_id
        ).all()
        
        correct_count = 0
        wrong_count = 0
        is_error_paper = session.session_type == 'paper_error'
        
        for record in records:
            question = db.query(Question).filter(Question.id == record.question_id).first()
            if not question:
                continue
            
            # 判断答案是否正确
            is_correct = ExamPaperService._check_answer(
                question.type.value,
                record.user_answer,
                question.answer
            )
            
            record.is_correct = 1 if is_correct else 0
            
            if is_correct:
                correct_count += 1
                if is_error_paper:
                    ErrorService.reduce_error_count(
                        db=db,
                        user_id=user_id,
                        question_id=record.question_id,
                        subject_id=session.subject_id
                    )
            else:
                wrong_count += 1
                
                # 更新错题集
                error = db.query(ErrorBook).filter(
                    ErrorBook.user_id == user_id,
                    ErrorBook.question_id == record.question_id
                ).first()
                
                if error:
                    error.wrong_count += 1
                    error.last_wrong_at = datetime.now()
                else:
                    error = ErrorBook(
                        user_id=user_id,
                        subject_id=session.subject_id,
                        question_id=record.question_id,
                        wrong_count=1
                    )
                    db.add(error)
        
        # 5. 计算成绩
        total_count = len(records)
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        grade = ExamPaperService._calculate_grade(accuracy)
        
        # 6. 更新会话状态
        session.status = 'completed'
        session.correct_count = correct_count
        session.wrong_count = wrong_count
        session.accuracy = f"{accuracy:.1f}"
        session.grade = grade
        session.completed_at = datetime.now()
        
        db.commit()

        invalidate_practice_related_cache(user_id)
        
        return {
            "score": correct_count * 2,  # 每题2分
            "accuracy": accuracy,
            "correct": correct_count,
            "wrong": wrong_count,
            "grade": grade
        }
    
    @staticmethod
    def check_expired_papers(db: Session) -> int:
        """
        检查并更新过期试卷（定时任务）
        :param db: 数据库会话
        :return: 更新的试卷数量
        """
        now = datetime.now()
        
        expired_sessions = db.query(PracticeSession).filter(
            PracticeSession.status == 'in_progress',
            PracticeSession.duration.isnot(None),
            PracticeSession.duration > 0,
            PracticeSession.expires_at.isnot(None),
            PracticeSession.expires_at < now
        ).all()
        
        count = 0
        for session in expired_sessions:
            session.status = 'expired'
            count += 1
        
        if count > 0:
            db.commit()
        
        return count
    
    # ============================================================
    # 私有辅助方法
    # ============================================================
    
    @staticmethod
    def _format_questions(questions: List[Question]) -> List[Dict[str, Any]]:
        """格式化题目列表"""
        result = []
        for q in questions:
            result.append({
                "id": q.id,
                "question": q.question,
                "type": q.type.value,
                "options": json.loads(q.options_json) if q.options_json else [],
                "score": 2  # 默认分值
            })
        return result
    
    @staticmethod
    def _check_answer(question_type: str, user_answer: str, correct_answer: str) -> bool:
        """检查答案是否正确"""
        if not user_answer:
            return False
        
        user_answer = user_answer.strip()
        correct_answer = correct_answer.strip()
        
        if question_type == 'multiple':
            # 多选题：排序后比较
            user_set = set(user_answer.split(','))
            correct_set = set(correct_answer.split(','))
            return user_set == correct_set
        else:
            # 其他题型：直接比较
            return user_answer.upper() == correct_answer.upper()
    
    @staticmethod
    def _calculate_grade(accuracy: float) -> str:
        """计算成绩等级"""
        if accuracy >= 90:
            return "A"
        elif accuracy >= 80:
            return "B"
        elif accuracy >= 70:
            return "C"
        elif accuracy >= 60:
            return "D"
        else:
            return "F"
