import json
from uuid import UUID

from redis import Redis

from app.config import settings


redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def enqueue_pipeline(project_id: UUID) -> str:
    payload = {"project_id": str(project_id)}
    redis_client.rpush(settings.pipeline_queue_name, json.dumps(payload))
    return settings.pipeline_queue_name


def enqueue_factory_brief(brief_id: UUID) -> str:
    queue_name = "factory_brief_queue"
    payload = {"factory_brief_id": str(brief_id)}
    redis_client.rpush(queue_name, json.dumps(payload))
    return queue_name
