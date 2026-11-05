import redis
import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class QueueManager:
    """
    Manages durable FIFO queues in Redis with pause/resume state control,
    job recovery, and graceful local fallback when Redis is offline.
    """
    def __init__(self):
        self.queue_name = "form141:jobs:pending"
        self.processing_queue = "form141:jobs:processing"
        self.state_key = "form141:queue:state"
        self._local_queue = []
        self._local_processing = set()
        self._local_state = "RUNNING"
        self._redis_client = None

    @property
    def client(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis connection unavailable, operating in local in-memory fallback: {e}")
                return None
        return self._redis_client

    def enqueue_job(self, job_id: int):
        """Pushes a job ID to the pending queue."""
        r = self.client
        if r:
            try:
                r.lpush(self.queue_name, str(job_id))
                logger.info(f"Enqueued job {job_id} to Redis")
                return
            except Exception as e:
                logger.error(f"Redis enqueue failed: {e}")
        
        # Fallback
        if job_id not in self._local_queue:
            self._local_queue.insert(0, job_id)
        logger.info(f"Enqueued job {job_id} to local queue")

    def claim_job(self) -> Optional[int]:
        """Claims a job for processing, respecting paused state."""
        if self.is_paused():
            return None

        r = self.client
        if r:
            try:
                job_id = r.blmove(
                    self.queue_name,
                    self.processing_queue,
                    src="RIGHT",
                    dest="LEFT",
                    timeout=2
                )
                if job_id:
                    return int(job_id)
            except Exception as e:
                logger.error(f"Redis claim error: {e}")
        
        # Fallback
        if self._local_queue:
            job_id = self._local_queue.pop()
            self._local_processing.add(job_id)
            return job_id
        return None

    def complete_job(self, job_id: int):
        """Removes job from processing queue."""
        r = self.client
        if r:
            try:
                r.lrem(self.processing_queue, 0, str(job_id))
                return
            except Exception as e:
                logger.error(f"Redis complete_job error: {e}")

        self._local_processing.discard(job_id)

    def pause_queue(self):
        r = self.client
        if r:
            try:
                r.set(self.state_key, "PAUSED")
            except Exception:
                pass
        self._local_state = "PAUSED"
        logger.info("Queue PAUSED")

    def resume_queue(self):
        r = self.client
        if r:
            try:
                r.set(self.state_key, "RUNNING")
            except Exception:
                pass
        self._local_state = "RUNNING"
        logger.info("Queue RESUMED")

    def stop_queue(self):
        r = self.client
        if r:
            try:
                r.set(self.state_key, "STOPPED")
            except Exception:
                pass
        self._local_state = "STOPPED"
        logger.info("Queue STOPPED")

    def start_queue(self):
        self.resume_queue()

    def get_state(self) -> str:
        r = self.client
        if r:
            try:
                state = r.get(self.state_key)
                if state:
                    return state
            except Exception:
                pass
        return self._local_state

    def is_paused(self) -> bool:
        return self.get_state() in ["PAUSED", "STOPPED"]

    def get_stats(self) -> Dict[str, Any]:
        r = self.client
        pending_len = 0
        proc_len = 0
        if r:
            try:
                pending_len = r.llen(self.queue_name)
                proc_len = r.llen(self.processing_queue)
            except Exception:
                pending_len = len(self._local_queue)
                proc_len = len(self._local_processing)
        else:
            pending_len = len(self._local_queue)
            proc_len = len(self._local_processing)

        return {
            "status": self.get_state(),
            "pending_count": pending_len,
            "processing_count": proc_len
        }

queue_manager = QueueManager()
