"""Shared cache invalidation helpers for frequently viewed data."""
from typing import Optional

from utils.redis_client import invalidate_cache


def invalidate_practice_related_cache(user_id: int) -> None:
    """Practice submissions affect history, home stats, errors, and rankings."""
    invalidate_cache(f"practice:user:{user_id}:*")
    invalidate_cache(f"error:user:{user_id}:*")
    invalidate_cache("leaderboard:*")


def invalidate_question_related_cache(
    user_id: int,
    subject_id: Optional[int] = None
) -> None:
    """Question mutations affect question lists and question statistics."""
    invalidate_cache(f"questions:user:{user_id}:*")
    if subject_id is not None:
        invalidate_cache(f"questions:subject:{subject_id}:*")
