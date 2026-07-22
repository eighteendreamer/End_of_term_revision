"""
排行榜服务
处理综合、校级、院级、专业、班级、个人排行榜
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import User, PracticeRecord
from datetime import datetime, timedelta


class LeaderboardService:
    """排行榜服务类"""

    @staticmethod
    def _calculate_user_score(db: Session, user_id: int, days: Optional[int] = None) -> Dict[str, Any]:
        """
        计算用户得分和统计数据（单条聚合查询，不再全量拉行）
        :param db: 数据库会话
        :param user_id: 用户ID
        :param days: 统计天数（None表示全部）
        :return: 用户统计数据
        """
        query = db.query(
            func.count(PracticeRecord.id),
            func.coalesce(func.sum(PracticeRecord.is_correct), 0),
        ).filter(PracticeRecord.user_id == user_id)

        # 如果指定天数，添加时间过滤
        if days:
            start_date = datetime.now() - timedelta(days=days)
            query = query.filter(PracticeRecord.created_at >= start_date)

        total_count, correct_count = query.one()
        total_count = int(total_count or 0)
        correct_count = int(correct_count or 0)
        wrong_count = total_count - correct_count

        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0

        # 计算综合得分：正确题数 * 1 + 正确率加成
        # 得分 = 正确题数 + (正确率/100) * 正确题数 * 0.5
        score = correct_count + (accuracy / 100) * correct_count * 0.5

        return {
            "user_id": user_id,
            "total_count": total_count,
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "accuracy": round(accuracy, 2),
            "score": round(score, 2)
        }

    @staticmethod
    def _get_user_info(db: Session, user_id: int) -> Dict[str, Any]:
        """
        获取用户信息
        :param db: 数据库会话
        :param user_id: 用户ID
        :return: 用户信息
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}

        return {
            "user_id": user.id,
            "username": user.username,
            "student_id": user.student_id,
            "school_id": user.school_id,
            "college_id": user.college_id,
            "major_id": user.major_id,
            "class_name": user.class_name
        }

    @staticmethod
    def _aggregate_leaderboard(
        db: Session,
        *,
        limit: int = 100,
        days: Optional[int] = None,
        school_id: Optional[int] = None,
        college_id: Optional[int] = None,
        major_id: Optional[int] = None,
        class_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        通用排行榜聚合：一条 GROUP BY 查询算出范围内所有用户统计，
        再用一条 IN 查询批量取用户信息，最后在内存中组装排名。

        :param db: 数据库会话
        :param limit: 返回数量限制
        :param days: 统计天数（None表示全部）
        :param school_id/college_id/major_id/class_name: 范围过滤（None表示不限）
        :return: 排行榜列表（已排序并带 rank）
        """
        needs_user_join = any(
            x is not None for x in (school_id, college_id, major_id, class_name)
        )

        agg_query = db.query(
            PracticeRecord.user_id.label("user_id"),
            func.count(PracticeRecord.id).label("total_count"),
            func.coalesce(func.sum(PracticeRecord.is_correct), 0).label("correct_count"),
        )

        # 范围榜通过 join users 在同一条 SQL 内完成过滤
        if needs_user_join:
            agg_query = agg_query.join(User, PracticeRecord.user_id == User.id)
            if school_id is not None:
                agg_query = agg_query.filter(User.school_id == school_id)
            if college_id is not None:
                agg_query = agg_query.filter(User.college_id == college_id)
            if major_id is not None:
                agg_query = agg_query.filter(User.major_id == major_id)
            if class_name is not None:
                agg_query = agg_query.filter(User.class_name == class_name)

        if days:
            start_date = datetime.now() - timedelta(days=days)
            agg_query = agg_query.filter(PracticeRecord.created_at >= start_date)

        rows = agg_query.group_by(PracticeRecord.user_id).all()
        if not rows:
            return []

        # 一次性批量取用户信息，避免逐用户查询
        user_ids = [row.user_id for row in rows]
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u for u in users}

        leaderboard: List[Dict[str, Any]] = []
        for row in rows:
            user = user_map.get(row.user_id)
            if not user:
                continue

            total_count = int(row.total_count or 0)
            correct_count = int(row.correct_count or 0)
            wrong_count = total_count - correct_count
            accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
            score = correct_count + (accuracy / 100) * correct_count * 0.5

            leaderboard.append({
                "user_id": user.id,
                "username": user.username,
                "student_id": user.student_id,
                "school_id": user.school_id,
                "college_id": user.college_id,
                "major_id": user.major_id,
                "class_name": user.class_name,
                "total_count": total_count,
                "correct_count": correct_count,
                "wrong_count": wrong_count,
                "accuracy": round(accuracy, 2),
                "score": round(score, 2),
            })

        # 按得分降序排序
        leaderboard.sort(key=lambda x: x["score"], reverse=True)

        # 添加排名
        for idx, item in enumerate(leaderboard[:limit], start=1):
            item["rank"] = idx

        return leaderboard[:limit]

    @staticmethod
    def get_comprehensive_leaderboard(
        db: Session,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取综合排行榜（所有用户）
        :param db: 数据库会话
        :param limit: 返回数量限制
        :param days: 统计天数（None表示全部）
        :return: 排行榜列表
        """
        return LeaderboardService._aggregate_leaderboard(db, limit=limit, days=days)

    @staticmethod
    def get_school_leaderboard(
        db: Session,
        school_id: int,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取校级排行榜（同一学校的用户）
        :param db: 数据库会话
        :param school_id: 学校ID
        :param limit: 返回数量限制
        :param days: 统计天数
        :return: 排行榜列表
        """
        return LeaderboardService._aggregate_leaderboard(
            db, limit=limit, days=days, school_id=school_id
        )

    @staticmethod
    def get_college_leaderboard(
        db: Session,
        college_id: int,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取院级排行榜（同一学院的用户）
        :param db: 数据库会话
        :param college_id: 学院ID
        :param limit: 返回数量限制
        :param days: 统计天数
        :return: 排行榜列表
        """
        return LeaderboardService._aggregate_leaderboard(
            db, limit=limit, days=days, college_id=college_id
        )

    @staticmethod
    def get_major_leaderboard(
        db: Session,
        major_id: int,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取专业排行榜（同一专业的用户）
        :param db: 数据库会话
        :param major_id: 专业ID
        :param limit: 返回数量限制
        :param days: 统计天数
        :return: 排行榜列表
        """
        return LeaderboardService._aggregate_leaderboard(
            db, limit=limit, days=days, major_id=major_id
        )

    @staticmethod
    def get_class_leaderboard(
        db: Session,
        school_id: int,
        college_id: int,
        major_id: int,
        class_name: str,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取班级排行榜（同一班级的用户）
        :param db: 数据库会话
        :param school_id: 学校ID
        :param college_id: 学院ID
        :param major_id: 专业ID
        :param class_name: 班级名称
        :param limit: 返回数量限制
        :param days: 统计天数
        :return: 排行榜列表
        """
        return LeaderboardService._aggregate_leaderboard(
            db,
            limit=limit,
            days=days,
            school_id=school_id,
            college_id=college_id,
            major_id=major_id,
            class_name=class_name,
        )

    @staticmethod
    def get_personal_stats(
        db: Session,
        user_id: int,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        获取个人统计数据和在各排行榜中的排名
        :param db: 数据库会话
        :param user_id: 用户ID
        :param days: 统计天数
        :return: 个人统计数据
        """
        user_info = LeaderboardService._get_user_info(db, user_id)
        if not user_info:
            return {}

        stats = LeaderboardService._calculate_user_score(db, user_id, days)

        # 获取在各排行榜中的排名
        result = {
            **user_info,
            **stats,
            "ranks": {}
        }

        # 综合排名
        comprehensive = LeaderboardService.get_comprehensive_leaderboard(db, limit=10000, days=days)
        for idx, item in enumerate(comprehensive, start=1):
            if item["user_id"] == user_id:
                result["ranks"]["comprehensive"] = idx
                break

        # 校级排名
        if user_info.get("school_id"):
            school = LeaderboardService.get_school_leaderboard(
                db, user_info["school_id"], limit=10000, days=days
            )
            for idx, item in enumerate(school, start=1):
                if item["user_id"] == user_id:
                    result["ranks"]["school"] = idx
                    break

        # 院级排名
        if user_info.get("college_id"):
            college = LeaderboardService.get_college_leaderboard(
                db, user_info["college_id"], limit=10000, days=days
            )
            for idx, item in enumerate(college, start=1):
                if item["user_id"] == user_id:
                    result["ranks"]["college"] = idx
                    break

        # 专业排名
        if user_info.get("major_id"):
            major = LeaderboardService.get_major_leaderboard(
                db, user_info["major_id"], limit=10000, days=days
            )
            for idx, item in enumerate(major, start=1):
                if item["user_id"] == user_id:
                    result["ranks"]["major"] = idx
                    break

        # 班级排名
        if all([
            user_info.get("school_id"),
            user_info.get("college_id"),
            user_info.get("major_id"),
            user_info.get("class_name")
        ]):
            class_board = LeaderboardService.get_class_leaderboard(
                db,
                user_info["school_id"],
                user_info["college_id"],
                user_info["major_id"],
                user_info["class_name"],
                limit=10000,
                days=days
            )
            for idx, item in enumerate(class_board, start=1):
                if item["user_id"] == user_id:
                    result["ranks"]["class"] = idx
                    break

        return result
