import logging
import os
import time
from typing import Optional

import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)


class WorkerQueueManager:
    def __init__(self):
        self.redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
        )

        self.pending_queue = "form141:jobs:pending"
        self.processing_queue = "form141:jobs:processing"
        self.state_key = "form141:queue:state"

        try:
            self.redis_client.ping()

            state = self.redis_client.get(self.state_key) or "UNKNOWN"
            length = self.redis_client.llen(self.pending_queue)

            logger.info(
                f"[WORKER] Redis connected ({REDIS_URL})"
            )
            logger.info(
                f"[WORKER] Queue = {self.pending_queue}"
            )
            logger.info(
                f"[WORKER] Queue state = {state}"
            )
            logger.info(
                f"[WORKER] Queue length = {length}"
            )

        except Exception as e:
            logger.warning(
                f"[WORKER] Redis connection check failed: {e}"
            )

    def is_paused(self) -> bool:
        try:
            state = self.redis_client.get(self.state_key)
            return state in ["PAUSED", "STOPPED"]

        except Exception:
            return False

    def enqueue_job(self, job_id: int):
        """Push a job ID back to the pending queue."""
        try:
            self.redis_client.lpush(
                self.pending_queue,
                str(job_id),
            )

            logger.info(
                f"Re-enqueued job {job_id} to "
                f"{self.pending_queue}"
            )

        except Exception as e:
            logger.error(
                f"Failed to enqueue job {job_id}: {e}"
            )

    def claim_job(self) -> Optional[int]:
        """
        Blocks briefly and safely moves a job from the
        pending queue to the processing queue.
        """
        if self.is_paused():
            return None

        try:
            job_id = self.redis_client.blmove(
                self.pending_queue,
                self.processing_queue,
                src="RIGHT",
                dest="LEFT",
                timeout=2,
            )

            if job_id:
                logger.info(
                    f"Claimed job {job_id} from queue."
                )
                return int(job_id)

        except Exception as e:
            logger.error(
                f"Redis error claiming job: {e}"
            )
            time.sleep(2)

        return None

    def complete_job(self, job_id: int):
        """Remove a completed job from the processing queue."""
        try:
            self.redis_client.lrem(
                self.processing_queue,
                0,
                str(job_id),
            )

            logger.info(
                f"Removed job {job_id} from processing queue."
            )

        except Exception as e:
            logger.error(
                f"Redis error removing job {job_id}: {e}"
            )


worker_queue = WorkerQueueManager()