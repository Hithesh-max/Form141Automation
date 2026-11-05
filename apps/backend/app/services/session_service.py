import os
import json
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import redis

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class SessionService:
    """
    Client-side session dispatcher used by FastAPI backend.
    Dispatches correlated RPC commands to the worker process owning Playwright browser contexts
    over Redis PubSub with dedicated response lists.
    """
    def __init__(self):
        self._redis_client = None

    @property
    def client(self):
        if self._redis_client is None:
            try:
                self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)
                self._redis_client.ping()
            except Exception as e:
                logger.debug(f"Redis unavailable for SessionService: {e}")
                self._redis_client = None
        return self._redis_client

    def send_command(self, job_id: int, command: str, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Publishes a correlated command to 'form141:browser:commands' and waits for a reply
        on a request-specific response queue 'form141:browser:response:{request_id}'.
        """
        r = self.client
        if not r:
            return {
                "request_id": None,
                "job_id": job_id,
                "command": command,
                "success": False,
                "session_available": False,
                "reason": "REDIS_OFFLINE"
            }

        request_id = f"req-{uuid.uuid4().hex[:10]}"
        payload = {
            "request_id": request_id,
            "job_id": job_id,
            "command": command,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        resp_key = f"form141:browser:response:{request_id}"
        try:
            r.publish("form141:browser:commands", json.dumps(payload))
            # Blocking pop on the dedicated response key
            raw_res = r.blpop(resp_key, timeout=int(max(1, timeout)))
            if raw_res:
                _, data_str = raw_res
                parsed = json.loads(data_str)
                # Clean up response key
                try:
                    r.delete(resp_key)
                except Exception:
                    pass
                return parsed
            else:
                logger.warning(f"Timeout waiting for worker response to {command} for job {job_id}")
                return {
                    "request_id": request_id,
                    "job_id": job_id,
                    "command": command,
                    "success": False,
                    "session_available": False,
                    "reason": "WORKER_TIMEOUT"
                }
        except Exception as e:
            logger.error(f"Error dispatching session command {command} for job {job_id}: {e}")
            return {
                "request_id": request_id,
                "job_id": job_id,
                "command": command,
                "success": False,
                "session_available": False,
                "reason": str(e)
            }

    def open_session(self, job_id: int) -> Dict[str, Any]:
        """Requests worker to bring the job's browser tab & window to the foreground."""
        r = self.client
        if r:
            try:
                raw_meta = r.get(f"form141:sessions:{job_id}")
                if not raw_meta:
                    return {
                        "request_id": None,
                        "job_id": job_id,
                        "command": "OPEN_SESSION",
                        "success": False,
                        "session_available": False,
                        "reason": "SESSION_UNAVAILABLE"
                    }
            except Exception:
                pass
        return self.send_command(job_id=job_id, command="OPEN_SESSION", timeout=3.5)

    def proceed_to_payment(self, job_id: int) -> Dict[str, Any]:
        """Requests worker to click Pay Now on the open preview page."""
        return self.send_command(job_id=job_id, command="PROCEED_TO_PAYMENT", timeout=15.0)

    def close_session(self, job_id: int) -> Dict[str, Any]:
        """Requests worker to close and clean up the job's browser session."""
        return self.send_command(job_id=job_id, command="CLOSE_SESSION", timeout=2.5)

    def check_session(self, job_id: int) -> Dict[str, Any]:
        """Checks if the browser session is currently active and unclosed."""
        # First check quick Redis key metadata
        r = self.client
        if r:
            try:
                raw_meta = r.get(f"form141:sessions:{job_id}")
                if not raw_meta:
                    return {
                        "job_id": job_id,
                        "success": True,
                        "session_available": False
                    }
            except Exception:
                pass
        return self.send_command(job_id=job_id, command="CHECK_SESSION", timeout=2.0)

    def get_session_metadata(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Reads safe runtime presence metadata from Redis."""
        r = self.client
        if not r:
            return None
        try:
            raw = r.get(f"form141:sessions:{job_id}")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

session_service = SessionService()
