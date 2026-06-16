"""
智能组卷服务
根据题型数量、多人作答统计、个人薄弱项、新鲜度和题目质量生成试卷。
"""
from collections import defaultdict
from datetime import datetime
import json
import random
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import ErrorBook, PracticeRecord, PracticeSession, Question
from services.question_service import QuestionService
from utils.redis_client import redis_client


class PaperGenerationService:
    """智能组卷服务。"""

    DIFFICULTY_RATIOS = {
        "easy": 0.3,
        "medium": 0.5,
        "hard": 0.2
    }

    @staticmethod
    def generate_questions(
        db: Session,
        user_id: int,
        subject_id: int,
        paper_type: str,
        question_counts: Dict[str, int]
    ) -> List[Question]:
        questions: List[Question] = []

        for question_type, count in question_counts.items():
            if count <= 0:
                continue

            if paper_type == "error":
                selected = PaperGenerationService._generate_error_questions(
                    db, user_id, subject_id, question_type, count
                )
            else:
                selected = PaperGenerationService._generate_normal_questions(
                    db, user_id, subject_id, question_type, count
                )

            questions.extend(selected)

        return questions

    @staticmethod
    def _generate_normal_questions(
        db: Session,
        user_id: int,
        subject_id: int,
        question_type: str,
        count: int
    ) -> List[Question]:
        candidates = db.query(Question).filter(
            Question.subject_id == subject_id,
            Question.type == question_type
        ).all()

        if len(candidates) < count:
            raise ValueError(f"{PaperGenerationService._type_label(question_type)}数量不足，需要 {count} 道，当前仅 {len(candidates)} 道")

        context = PaperGenerationService._build_scoring_context(
            db, user_id, subject_id, question_type, candidates
        )
        scored = [
            PaperGenerationService._score_question(question, context)
            for question in candidates
            if PaperGenerationService._quality_score(question) > 0
        ]

        return PaperGenerationService._select_by_difficulty(scored, count)

    @staticmethod
    def _generate_error_questions(
        db: Session,
        user_id: int,
        subject_id: int,
        question_type: str,
        count: int
    ) -> List[Question]:
        rows = db.query(Question, ErrorBook).join(
            ErrorBook, ErrorBook.question_id == Question.id
        ).filter(
            ErrorBook.user_id == user_id,
            ErrorBook.subject_id == subject_id,
            Question.type == question_type
        ).all()

        if len(rows) < count:
            raise ValueError(f"{PaperGenerationService._type_label(question_type)}错题数量不足，需要 {count} 道，当前仅 {len(rows)} 道")

        candidates = [question for question, _ in rows]
        context = PaperGenerationService._build_scoring_context(
            db, user_id, subject_id, question_type, candidates
        )
        error_map = {question.id: error for question, error in rows}

        scored = []
        for question in candidates:
            error = error_map[question.id]
            base = PaperGenerationService._score_question(question, context)
            recency_bonus = PaperGenerationService._days_score(error.last_wrong_at, recent_is_better=True)
            base["score"] += min(80, error.wrong_count * 20) + recency_bonus
            scored.append(base)

        return PaperGenerationService._weighted_take(scored, count)

    @staticmethod
    def _build_scoring_context(
        db: Session,
        user_id: int,
        subject_id: int,
        question_type: str,
        candidates: List[Question]
    ) -> Dict[str, Any]:
        question_ids = [q.id for q in candidates]

        return {
            "global_stats": PaperGenerationService._get_global_stats(db, subject_id, question_type),
            "user_question_stats": PaperGenerationService._get_user_question_stats(db, user_id, question_ids),
            "error_map": PaperGenerationService._get_error_map(db, user_id, question_ids),
            "recent_question_ids": PaperGenerationService._get_recent_paper_question_ids(db, user_id, subject_id),
            "type_weakness": PaperGenerationService._get_user_type_weakness(db, user_id, subject_id)
        }

    @staticmethod
    def _get_global_stats(db: Session, subject_id: int, question_type: str) -> Dict[int, Dict[str, int]]:
        cache_key = f"paper:stats:subject:{subject_id}:type:{question_type}:global"
        cached = redis_client.get(cache_key)
        if cached is not None:
            return {int(k): v for k, v in cached.items()}

        rows = db.query(
            PracticeRecord.question_id,
            func.count(PracticeRecord.id).label("total"),
            func.sum(PracticeRecord.is_correct).label("correct")
        ).join(
            Question, Question.id == PracticeRecord.question_id
        ).filter(
            PracticeRecord.subject_id == subject_id,
            Question.type == question_type
        ).group_by(PracticeRecord.question_id).all()

        stats = {
            row.question_id: {
                "total": int(row.total or 0),
                "correct": int(row.correct or 0)
            }
            for row in rows
        }
        redis_client.set(cache_key, stats, expire=600)
        return stats

    @staticmethod
    def _get_user_question_stats(db: Session, user_id: int, question_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not question_ids:
            return {}

        rows = db.query(
            PracticeRecord.question_id,
            func.count(PracticeRecord.id).label("total"),
            func.sum(PracticeRecord.is_correct).label("correct"),
            func.max(PracticeRecord.created_at).label("last_seen")
        ).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.question_id.in_(question_ids)
        ).group_by(PracticeRecord.question_id).all()

        return {
            row.question_id: {
                "total": int(row.total or 0),
                "correct": int(row.correct or 0),
                "last_seen": row.last_seen
            }
            for row in rows
        }

    @staticmethod
    def _get_error_map(db: Session, user_id: int, question_ids: List[int]) -> Dict[int, ErrorBook]:
        if not question_ids:
            return {}

        rows = db.query(ErrorBook).filter(
            ErrorBook.user_id == user_id,
            ErrorBook.question_id.in_(question_ids)
        ).all()
        return {row.question_id: row for row in rows}

    @staticmethod
    def _get_recent_paper_question_ids(db: Session, user_id: int, subject_id: int) -> Set[int]:
        sessions = db.query(PracticeSession.id).filter(
            PracticeSession.user_id == user_id,
            PracticeSession.subject_id == subject_id,
            PracticeSession.session_type.in_(["paper_normal", "paper_error"])
        ).order_by(PracticeSession.created_at.desc()).limit(3).all()

        session_ids = [row.id for row in sessions]
        if not session_ids:
            return set()

        rows = db.query(PracticeRecord.question_id).filter(
            PracticeRecord.session_id.in_(session_ids)
        ).all()
        return {row.question_id for row in rows}

    @staticmethod
    def _get_user_type_weakness(db: Session, user_id: int, subject_id: int) -> Dict[str, float]:
        cache_key = f"paper:user:{user_id}:subject:{subject_id}:type_weakness"
        cached = redis_client.get(cache_key)
        if cached is not None:
            return cached

        rows = db.query(
            Question.type,
            func.count(PracticeRecord.id).label("total"),
            func.sum(PracticeRecord.is_correct).label("correct")
        ).join(
            Question, Question.id == PracticeRecord.question_id
        ).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.subject_id == subject_id
        ).group_by(Question.type).all()

        result = {}
        for row in rows:
            total = int(row.total or 0)
            correct = int(row.correct or 0)
            accuracy = correct / total if total else 1
            result[row.type.value if hasattr(row.type, "value") else row.type] = round((1 - accuracy) * 20, 2)

        redis_client.set(cache_key, result, expire=300)
        return result

    @staticmethod
    def _score_question(question: Question, context: Dict[str, Any]) -> Dict[str, Any]:
        global_stats = context["global_stats"].get(question.id, {})
        user_stats = context["user_question_stats"].get(question.id, {})
        error = context["error_map"].get(question.id)

        weak_score = 0
        if error:
            weak_score += 40 + min(60, error.wrong_count * 15)
        if user_stats.get("total"):
            user_accuracy = user_stats["correct"] / user_stats["total"]
            weak_score += (1 - user_accuracy) * 30
        weak_score += context["type_weakness"].get(question.type.value, 0)

        fresh_score = PaperGenerationService._freshness_score(
            user_stats.get("last_seen"),
            question.id in context["recent_question_ids"]
        )
        quality_score = PaperGenerationService._quality_score(question)
        difficulty = PaperGenerationService._difficulty(question, global_stats)
        difficulty_score = 70 if difficulty == "medium" else 55

        total_score = (
            weak_score * 0.40
            + fresh_score * 0.25
            + difficulty_score * 0.20
            + quality_score * 0.15
            + random.uniform(0, 10)
        )

        return {
            "question": question,
            "difficulty": difficulty,
            "score": max(1, total_score)
        }

    @staticmethod
    def _select_by_difficulty(scored: List[Dict[str, Any]], count: int) -> List[Question]:
        if len(scored) < count:
            raise ValueError(f"可用高质量题目不足，需要 {count} 道，当前仅 {len(scored)} 道")

        by_difficulty: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in scored:
            by_difficulty[item["difficulty"]].append(item)

        quotas = PaperGenerationService._difficulty_quotas(count)
        selected: List[Question] = []
        selected_ids: Set[int] = set()

        for difficulty, quota in quotas.items():
            picked = PaperGenerationService._weighted_take(by_difficulty[difficulty], quota, selected_ids)
            selected.extend(picked)
            selected_ids.update(q.id for q in picked)

        remaining = count - len(selected)
        if remaining > 0:
            picked = PaperGenerationService._weighted_take(scored, remaining, selected_ids)
            selected.extend(picked)

        return selected

    @staticmethod
    def _difficulty_quotas(count: int) -> Dict[str, int]:
        raw = {k: count * v for k, v in PaperGenerationService.DIFFICULTY_RATIOS.items()}
        quotas = {k: int(v) for k, v in raw.items()}
        while sum(quotas.values()) < count:
            key = max(raw, key=lambda k: raw[k] - quotas[k])
            quotas[key] += 1
        return quotas

    @staticmethod
    def _weighted_take(
        scored: List[Dict[str, Any]],
        count: int,
        excluded_ids: Optional[Set[int]] = None
    ) -> List[Question]:
        excluded_ids = excluded_ids or set()
        pool = [item for item in scored if item["question"].id not in excluded_ids]
        pool = sorted(pool, key=lambda item: item["score"], reverse=True)[:max(count * 3, count)]

        picked: List[Question] = []
        while pool and len(picked) < count:
            weights = [item["score"] for item in pool]
            chosen = random.choices(pool, weights=weights, k=1)[0]
            picked.append(chosen["question"])
            pool.remove(chosen)

        return picked

    @staticmethod
    def _difficulty(question: Question, global_stats: Dict[str, int]) -> str:
        if global_stats.get("total", 0) >= 3:
            accuracy = global_stats["correct"] / global_stats["total"]
            if accuracy >= 0.8:
                return "easy"
            if accuracy < 0.4:
                return "hard"
            return "medium"

        return getattr(question, "difficulty_level", None) or "medium"

    @staticmethod
    def _quality_score(question: Question) -> int:
        stored = getattr(question, "quality_score", None)
        if stored is not None:
            return int(stored)

        options = PaperGenerationService._options(question)
        return QuestionService.calculate_quality_score(
            question.type.value,
            question.question,
            options,
            question.answer,
            question.analysis
        )

    @staticmethod
    def _options(question: Question) -> List[str]:
        if not question.options_json:
            return []
        if isinstance(question.options_json, list):
            return question.options_json
        try:
            return json.loads(question.options_json)
        except Exception:
            return []

    @staticmethod
    def _freshness_score(last_seen: Optional[datetime], in_recent_paper: bool) -> float:
        if in_recent_paper:
            return 0
        if not last_seen:
            return 100

        days = (datetime.now() - last_seen).days
        if days >= 30:
            return 85
        if days >= 7:
            return 65
        if days >= 3:
            return 35
        return 10

    @staticmethod
    def _days_score(value: Optional[datetime], recent_is_better: bool = False) -> float:
        if not value:
            return 0
        days = (datetime.now() - value).days
        if recent_is_better:
            if days <= 1:
                return 30
            if days <= 7:
                return 20
            return 10
        return min(30, days)

    @staticmethod
    def _type_label(question_type: str) -> str:
        return {
            "single": "单选题",
            "multiple": "多选题",
            "judge": "判断题",
            "fill": "填空题",
            "major": "大型题"
        }.get(question_type, question_type)
