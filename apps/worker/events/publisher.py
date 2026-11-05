import json
import logging
import os
from datetime import datetime, timezone
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)

async def publish_event(event_type: str, job_id: str, status: str, message: str):
    """Publishes a real-time event to the Redis pub/sub channel."""
    event = {
        "event": event_type,
        "job_id": job_id,
        "status": status,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        await redis_client.publish("form141:events", json.dumps(event))
        logger.info(f"Published event: {event_type} - {status}")
    except Exception as e:
        logger.debug(f"Redis publish skipped (offline or testing): {e}")
