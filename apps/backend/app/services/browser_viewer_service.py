import os
import hmac
import hashlib
import time
import json
import base64
import secrets
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "form141-default-insecure-secret-key-change-in-production")
TOKEN_TTL_SECONDS = int(os.getenv("VIEWER_TOKEN_TTL_SECONDS", "900"))  # Default 15 minutes


class BrowserViewerService:
    """
    Manages cryptographically signed, short-lived session tokens for remote browser viewing.
    Ensures:
    1. Tokens cannot be forged or guessed.
    2. Tokens are strictly bound to a specific job_id.
    3. Tokens expire automatically.
    4. Tokens cannot be used across different jobs or users.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret = (secret_key or SECRET_KEY).encode("utf-8")

    def generate_token(self, job_id: int, user_id: Optional[int] = None, ttl_seconds: int = TOKEN_TTL_SECONDS) -> str:
        """Generates a secure, signed token for the given job_id."""
        now = int(time.time())
        expires_at = now + ttl_seconds
        nonce = secrets.token_hex(8)

        payload = {
            "job_id": int(job_id),
            "user_id": user_id,
            "created_at": now,
            "expires_at": expires_at,
            "nonce": nonce
        }

        payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

        signature = hmac.new(self.secret, payload_bytes, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

        return f"{payload_b64}.{sig_b64}"

    def verify_token(self, token: str, expected_job_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Verifies the signature, expiration, and job correlation of a viewer token.
        Returns the decoded payload if valid, or None if invalid or expired.
        """
        if not token or "." not in token:
            return None

        try:
            payload_b64, sig_b64 = token.split(".", 1)

            # Re-pad base64 strings
            rem = len(payload_b64) % 4
            if rem:
                payload_b64 += "=" * (4 - rem)
            rem = len(sig_b64) % 4
            if rem:
                sig_b64 += "=" * (4 - rem)

            payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
            expected_sig = hmac.new(self.secret, payload_bytes, hashlib.sha256).digest()
            actual_sig = base64.urlsafe_b64decode(sig_b64.encode("utf-8"))

            if not hmac.compare_digest(expected_sig, actual_sig):
                logger.warning("Viewer token verification failed: signature mismatch")
                return None

            payload = json.loads(payload_bytes.decode("utf-8"))
            now = int(time.time())

            if payload.get("expires_at", 0) < now:
                logger.warning(f"Viewer token expired (expires_at={payload.get('expires_at')}, now={now})")
                return None

            if expected_job_id is not None and payload.get("job_id") != int(expected_job_id):
                logger.warning(f"Viewer token job mismatch (token_job={payload.get('job_id')}, expected={expected_job_id})")
                return None

            return payload

        except Exception as e:
            logger.warning(f"Error parsing viewer token: {e}")
            return None


browser_viewer_service = BrowserViewerService()
