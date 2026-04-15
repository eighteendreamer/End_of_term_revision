"""
练习服务
处理练习记录、统计等
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.models import PracticeRecord, PracticeSession, Question
from datetime import datetime, timedelta


class PracticeService:
    """练习服务类"""
    
    @staticmethod
    def create_practice_session(
        db: Session,
        user_id: int,
        subject_id: int,
        total_count: int,
        correct_count: int,
        wrong_count: int,
        accuracy: float,
        grade: str
    ) -> int:
        """
        创建练习会话记录
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param total_count: 总题数
        :param correct_count: 正确题数
        :param wrong_count: 错误题数
        :param accuracy: 正确率
        :param grade: 成绩等级
        :return: 会话 ID
        """
        session = PracticeSession(
            user_id=user_id,
            subject_id=subject_id,
            total_count=total_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            accuracy=str(accuracy),
            grade=grade
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return session.id
    
    @staticmethod
    def create_practice_record(
        db: Session,
        session_id: int,
        user_id: int,
        subject_id: int,
        question_id: int,
        user_answer: str,
        is_correct: bool
    ) -> PracticeRecord:
        """
        创建练习记录
        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param question_id: 题目 ID
        :param user_answer: 用户答案
        :param is_correct: 是否正确
        :return: PracticeRecord 实例
        """
        record = PracticeRecord(
            session_id=session_id,
            user_id=user_id,
            subject_id=subject_id,
            question_id=question_id,
            user_answer=user_answer,
            is_correct=1 if is_correct else 0
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return record
    
    @staticmethod
    def batch_create_records(
        db: Session,
        user_id: int,
        subject_id: int,
        answers: List[Dict[str, Any]]
    ) -> List[PracticeRecord]:
        """
        批量创建练习记录
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param answers: 答案列表，格式 [{"question_id": 1, "user_answer": "A", "is_correct": True}]
        :return: PracticeRecord 列表
        """
        records = []
        
        for ans in answers:
            record = PracticeService.create_practice_record(
                db=db,
                user_id=user_id,
                subject_id=subject_id,
                question_id=ans["question_id"],
                user_answer=ans["user_answer"],
                is_correct=ans["is_correct"]
            )
            records.append(record)
        
        return records
    
    @staticmethod
    def get_statistics(db: Session, user_id: int, days: Optional[int] = None) -> Dict[str, Any]:
        """
        获取练习统计数据
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param days: 统计最近几天（None 表示全部）
        :return: 统计数据字典
        """
        query = db.query(PracticeRecord).filter(PracticeRecord.user_id == user_id)
        
        # 如果指定天数，添加时间过滤
        if days:
            start_date = datetime.now() - timedelta(days=days)
            query = query.filter(PracticeRecord.created_at >= start_date)
        
        records = query.all()
        
        total_count = len(records)
        correct_count = sum(1 for r in records if r.is_correct == 1)
        wrong_count = total_count - correct_count
        
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        
        # 计算等级
        grade = PracticeService._calculate_grade(accuracy)
        
        return {
            "total_count": total_count,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "accuracy": round(accuracy, 2),
            "grade": grade
        }
    
    @staticmethod
    def _calculate_grade(accuracy: float) -> str:
        """
        根据正确率计算等级
        :param accuracy: 正确率
        :return: 等级 A-F
        """
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
    
    @staticmethod
    def get_today_statistics(db: Session, user_id: int) -> Dict[str, Any]:
        """
        获取今日统计（从今天0点开始）
        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 今日统计数据
        """
        # 获取今天0点的时间
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        query = db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.created_at >= today_start
        )
        
        records = query.all()
        
        total_count = len(records)
        correct_count = sum(1 for r in records if r.is_correct == 1)
        wrong_count = total_count - correct_count
        
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        grade = PracticeService._calculate_grade(accuracy)
        
        return {
            "total_count": total_count,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "accuracy": round(accuracy, 2),
            "grade": grade
        }
    
    @staticmethod
    def get_week_statistics(db: Session, user_id: int) -> Dict[str, Any]:
        """
        获取本周统计（从本周一0点开始）
        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 本周统计数据
        """
        # 获取本周一0点的时间
        now = datetime.now()
        # weekday(): 0=周一, 6=周日
        days_since_monday = now.weekday()
        monday_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
        
        query = db.query(PracticeRecord).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.created_at >= monday_start
        )
        
        records = query.all()
        
        total_count = len(records)
        correct_count = sum(1 for r in records if r.is_correct == 1)
        wrong_count = total_count - correct_count
        
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        grade = PracticeService._calculate_grade(accuracy)
        
        return {
            "total_count": total_count,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "accuracy": round(accuracy, 2),
            "grade": grade
        }
    
    @staticmethod
    def get_all_statistics(db: Session, user_id: int) -> Dict[str, Any]:
        """
        获取全部统计
        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 全部统计数据
        """
        return PracticeService.get_statistics(db, user_id, days=None)
    
    @staticmethod
    def get_consecutive_days(db: Session, user_id: int) -> int:
        """
        获取连续学习天数
        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 连续天数
        """
        # 获取所有练习日期（去重）
        dates = db.query(
            func.date(PracticeRecord.created_at).label('practice_date')
        ).filter(
            PracticeRecord.user_id == user_id
        ).distinct().order_by(
            func.date(PracticeRecord.created_at).desc()
        ).all()
        
        if not dates:
            return 0
        
        # 检查今天是否有练习
        today = datetime.now().date()
        date_list = [d[0] for d in dates]
        
        if today not in date_list:
            return 0
        
        # 计算连续天数
        consecutive = 1
        current_date = today
        
        for i in range(1, len(date_list)):
            expected_date = current_date - timedelta(days=1)
            if date_list[i] == expected_date:
                consecutive += 1
                current_date = expected_date
            else:
                break
        
        return consecutive
    
    @staticmethod
    def check_answer(question: Question, user_answer: str) -> bool:
        """
        检查答案是否正确（宽松模式）
        :param question: 题目对象
        :param user_answer: 用户答案
        :return: 是否正确
        """
        # 获取正确答案和用户答案，去除首尾空格
        correct_answer = question.answer.strip()
        user_answer = user_answer.strip()
        
        # 多选题：提取所有选项字母，忽略分隔符和空格
        if question.type.value == "multiple":
            # 提取所有大写字母作为选项
            import re
            correct_options = set(re.findall(r'[A-Z]', correct_answer.upper()))
            user_options = set(re.findall(r'[A-Z]', user_answer.upper()))
            return correct_options == user_options
        
        # 填空题：宽松比对，忽略空格和标点符号
        if question.type.value == "fill":
            # 移除所有空格
            correct_clean = correct_answer.replace(' ', '').replace('\u3000', '')  # 移除普通空格和全角空格
            user_clean = user_answer.replace(' ', '').replace('\u3000', '')
            
            # 统一分隔符：将所有可能的分隔符替换为统一的分隔符
            import re
            # 常见分隔符：顿号、逗号、分号、斜杠、竖线等
            separators = r'[、，,；;/|]'
            
            # 提取所有答案片段（按分隔符分割）
            correct_parts = [p.strip() for p in re.split(separators, correct_clean) if p.strip()]
            user_parts = [p.strip() for p in re.split(separators, user_clean) if p.strip()]
            
            # 如果没有分隔符，直接比较整体
            if len(correct_parts) == 1 and len(user_parts) == 1:
                return correct_parts[0].upper() == user_parts[0].upper()
            
            # 有多个答案片段，比较集合（不考虑顺序）
            return set(p.upper() for p in correct_parts) == set(p.upper() for p in user_parts)
        
        # 其他题型（单选、判断）：去除空格后比较
        correct_clean = correct_answer.replace(' ', '').upper()
        user_clean = user_answer.replace(' ', '').upper()
        
        return correct_clean == user_clean
