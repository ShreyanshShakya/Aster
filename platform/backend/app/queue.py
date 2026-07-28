import json
from uuid import UUID

import redis

from app.core.config import get_settings

QUEUE_KEY = "aster:jobs"


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def enqueue_job(job_id: UUID) -> None:
    redis_client().rpush(QUEUE_KEY, str(job_id))


def pop_job(timeout_seconds: int = 5) -> UUID | None:
    item = redis_client().blpop(QUEUE_KEY, timeout=timeout_seconds)
    return UUID(item[1]) if item else None


def publish_event(job_id: UUID, event: dict) -> None:
    redis_client().publish(f"aster:jobs:{job_id}", json.dumps(event))


def publish_user_event(user_id: UUID, event: dict) -> None:
    redis_client().publish(f"aster:users:{user_id}", json.dumps(event))
