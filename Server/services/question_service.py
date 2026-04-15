"""
题目服务
题目的增删改查
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import Question, Subject
import json


class QuestionService:
    """题目服务类"""

    @staticmethod
    def auto_judge_fill_type(question: str, options: list, question_type: str) -> bool:
        """
        自动判定是否为填空题：题干含下划线或括号，且无选项，且不是判断题
        :param question: 题干内容
        :param options: 选项列表
        :param question_type: 题目类型
        :return: 是否为填空题
        """
        if question_type == 'judge':
            return False
        if options and len(options) > 0:
            return False
        has_blank = False
        if "___" in question or "____" in question or "_____" in question:
            has_blank = True
        if "（）" in question or "( )" in question:
            has_blank = True
        return has_blank

    @staticmethod
    def create_question(
        db: Session,
        user_id: int,
        subject_id: int,
        question_type: str,
        question: str,
        options: List[str],
        answer: str,
        analysis: str,
        adjacent_question_type: Optional[str] = None
    ) -> Question:
        """
        创建题目
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param question_type: 题目类型
        :param question: 题干
        :param options: 选项列表
        :param answer: 答案
        :param analysis: 解析
        :return: Question 实例
        """
        # 获取科目的组织架构信息
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        school_id = subject.school_id if subject else None
        college_id = subject.college_id if subject else None
        major_id = subject.major_id if subject else None
        
        options_json = json.dumps(options, ensure_ascii=False) if options else None

        auto_fill = QuestionService.auto_judge_fill_type(question, options, question_type)
        if auto_fill and adjacent_question_type == 'major':
            if "求置信区间" in question or "求概率" in question:
                auto_fill = False

        final_type = question_type

        if auto_fill:
            final_type = 'fill'
        elif question_type == 'fill':
            text = (question or "").strip()
            has_blank = False
            if "___" in text or "____" in text or "_____" in text:
                has_blank = True
            if "（）" in text or "( )" in text:
                has_blank = True
            if not has_blank and len(text) > 40:
                final_type = 'major'

        # 创建题目，自动继承科目的组织架构信息
        db_question = Question(
            user_id=user_id,
            subject_id=subject_id,
            school_id=school_id,
            college_id=college_id,
            major_id=major_id,
            type=final_type,
            question=question,
            options_json=options_json,
            answer=answer,
            analysis=analysis
        )
        
        db.add(db_question)
        db.flush()  # 只flush，不commit，由调用者决定何时commit
        db.refresh(db_question)
        
        return db_question
    
    @staticmethod
    def get_question_by_id(db: Session, question_id: int, user_id: int = None) -> Optional[Question]:
        """
        根据 ID 获取题目
        :param db: 数据库会话
        :param question_id: 题目 ID
        :param user_id: 用户 ID（可选，用于数据隔离验证）
        :return: Question 实例或 None
        """
        query = db.query(Question).filter(Question.id == question_id)
        if user_id is not None:
            query = query.filter(Question.user_id == user_id)
        return query.first()
    
    @staticmethod
    def get_questions_by_subject(
        db: Session,
        user_id: int,
        subject_id: Optional[int] = None,
        question_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[Question]:
        """
        获取题目列表（支持分页）
        支持查询共享科目的题目
        
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID（可选，不传则查询所有可访问的题目）
        :param question_type: 题目类型（可选）
        :param page: 页码（从1开始，默认1）
        :param page_size: 每页数量（默认20）
        :return: Question 列表
        """
        from services.share_service import ShareService
        
        # 如果指定了科目，检查权限
        if subject_id is not None:
            if not ShareService.can_access_subject(user_id, subject_id, db):
                return []  # 无权访问，返回空列表
            
            # 查询指定科目的题目
            query = db.query(Question).filter(
                Question.subject_id == subject_id
            )
        else:
            # 获取用户可访问的所有科目
            accessible_subjects = ShareService.get_accessible_subjects(user_id, db)
            subject_ids = [s['id'] for s in accessible_subjects]
            
            if not subject_ids:
                return []  # 没有可访问的科目
            
            # 查询所有可访问科目的题目
            query = db.query(Question).filter(
                Question.subject_id.in_(subject_ids)
            )
        
        if question_type:
            query = query.filter(Question.type == question_type)
        
        # 计算偏移量
        offset = (page - 1) * page_size
        
        # 应用分页，按ID正序（从第一条开始）
        query = query.order_by(Question.id.asc()).offset(offset).limit(page_size)
        
        return query.all()
    
    @staticmethod
    def get_random_questions(
        db: Session,
        user_id: int,
        subject_id: int,
        question_counts: Dict[str, int]
    ) -> List[Question]:
        """
        随机获取指定数量的题目
        支持共享科目：只按 subject_id 查询，不过滤 user_id
        权限检查由调用方（practice_router）在 ShareService 中完成
        
        :param db: 数据库会话
        :param user_id: 用户 ID（保留参数兼容性，但不用于过滤）
        :param subject_id: 科目 ID
        :param question_counts: 题目类型和数量的字典，例如 {"single": 10, "multiple": 5}
        :return: Question 列表
        """
        questions = []
        
        for question_type, count in question_counts.items():
            if count > 0:
                # 只按 subject_id 查询，不过滤 user_id，支持共享题库
                type_questions = db.query(Question).filter(
                    Question.subject_id == subject_id,
                    Question.type == question_type
                ).order_by(func.rand()).limit(count).all()
                
                questions.extend(type_questions)
        
        return questions
    
    @staticmethod
    def delete_question(db: Session, question_id: int, user_id: int = None) -> bool:
        """
        删除题目
        :param db: 数据库会话
        :param question_id: 题目 ID
        :param user_id: 用户 ID（可选，用于数据隔离验证）
        :return: 是否删除成功
        """
        query = db.query(Question).filter(Question.id == question_id)
        if user_id is not None:
            query = query.filter(Question.user_id == user_id)
        question = query.first()
        if question:
            db.delete(question)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_question_types_by_subject(db: Session, user_id: int, subject_id: int) -> List[str]:
        """
        获取科目下的所有题目类型
        支持共享科目：只按 subject_id 查询
        
        :param db: 数据库会话
        :param user_id: 用户 ID（保留参数兼容性）
        :param subject_id: 科目 ID
        :return: 题目类型列表
        """
        # 只按 subject_id 查询，支持共享题库
        types = db.query(Question.type).filter(
            Question.subject_id == subject_id
        ).distinct().all()
        
        return [t[0].value for t in types]
    
    @staticmethod
    def get_question_statistics(db: Session, user_id: int, subject_id: Optional[int] = None) -> Dict[str, int]:
        """
        获取题目数量统计
        支持统计共享科目的题目
        
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID（可选，不传则统计所有可访问的题目）
        :return: 题目统计字典，包含总数和各题型数量
        """
        from services.share_service import ShareService
        
        # 如果指定了科目，检查权限
        if subject_id is not None:
            if not ShareService.can_access_subject(user_id, subject_id, db):
                return {
                    "total": 0,
                    "single": 0,
                    "multiple": 0,
                    "judge": 0,
                    "fill": 0,
                    "major": 0
                }
            
            # 统计指定科目的题目
            query = db.query(Question).filter(
                Question.subject_id == subject_id
            )
        else:
            # 获取用户可访问的所有科目
            accessible_subjects = ShareService.get_accessible_subjects(user_id, db)
            subject_ids = [s['id'] for s in accessible_subjects]
            
            if not subject_ids:
                return {
                    "total": 0,
                    "single": 0,
                    "multiple": 0,
                    "judge": 0,
                    "fill": 0,
                    "major": 0
                }
            
            # 统计所有可访问科目的题目
            query = db.query(Question).filter(
                Question.subject_id.in_(subject_ids)
            )
        
        # 查询总题目数
        total_count = query.count()
        
        # 查询各题型数量
        type_counts_query = db.query(
            Question.type,
            func.count(Question.id)
        )
        
        if subject_id is not None:
            type_counts_query = type_counts_query.filter(Question.subject_id == subject_id)
        else:
            accessible_subjects = ShareService.get_accessible_subjects(user_id, db)
            subject_ids = [s['id'] for s in accessible_subjects]
            if subject_ids:
                type_counts_query = type_counts_query.filter(Question.subject_id.in_(subject_ids))
        
        type_counts = type_counts_query.group_by(Question.type).all()
        
        # 构建统计结果
        statistics = {
            "total": total_count or 0,
            "single": 0,
            "multiple": 0,
            "judge": 0,
            "fill": 0,
            "major": 0
        }
        
        for question_type, count in type_counts:
            statistics[question_type.value] = count
        
        return statistics
    
    @staticmethod
    def check_duplicate_question(
        db: Session,
        user_id: int,
        subject_id: int,
        question_text: str,
        question_type: str
    ) -> bool:
        """
        检查题目是否已存在（去重）
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param question_text: 题干文本
        :param question_type: 题目类型
        :return: True 表示已存在，False 表示不存在
        """
        existing = db.query(Question).filter(
            Question.user_id == user_id,
            Question.subject_id == subject_id,
            Question.question == question_text,
            Question.type == question_type
        ).first()
        
        return existing is not None
    
    @staticmethod
    def batch_create_questions(
        db: Session,
        user_id: int,
        subject_id: int,
        questions_data: List[Dict[str, Any]],
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        批量创建题目（支持去重）
        :param db: 数据库会话
        :param user_id: 用户 ID
        :param subject_id: 科目 ID
        :param questions_data: 题目数据列表
        :param skip_duplicates: 是否跳过重复题目（默认True）
        :return: 包含创建结果的字典
        """
        created_questions = []
        skipped_count = 0
        
        total = len(questions_data)
        for index, q_data in enumerate(questions_data):
            # 检查是否重复
            if skip_duplicates and QuestionService.check_duplicate_question(
                db, user_id, subject_id, q_data["question"], q_data["type"]
            ):
                skipped_count += 1
                print(f"[去重] 跳过重复题目: {q_data['question'][:50]}...")
                continue

            prev_type = None
            next_type = None
            if index > 0:
                prev_type = questions_data[index - 1].get("type")
            if index + 1 < total:
                next_type = questions_data[index + 1].get("type")
            adjacent_question_type = None
            if prev_type == "major" or next_type == "major":
                adjacent_question_type = "major"

            question = QuestionService.create_question(
                db=db,
                user_id=user_id,
                subject_id=subject_id,
                question_type=q_data["type"],
                question=q_data["question"],
                options=q_data.get("options", []),
                answer=q_data["answer"],
                analysis=q_data["analysis"],
                adjacent_question_type=adjacent_question_type
            )
            created_questions.append(question)
        
        # 统一提交所有新创建的题目
        db.commit()
        
        return {
            "created": created_questions,
            "created_count": len(created_questions),
            "skipped_count": skipped_count,
            "total_input": len(questions_data)
        }
