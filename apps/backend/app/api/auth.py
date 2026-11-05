import os
import time
import json
import base64
import hmac
import hashlib
import secrets
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from apps.backend.app.database.config import get_db
from apps.backend.app.database import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY", "form141-default-insecure-secret-key-change-in-production")
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", "86400"))  # 24 hours

security_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or ":" not in stored_hash:
        return False
    salt, _ = stored_hash.split(":", 1)
    return hash_password(password, salt) == stored_hash


def create_access_token(user_id: int, username: str, role: str, expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS) -> str:
    """Generates a verifiable, cryptographically signed bearer token."""
    now = int(time.time())
    expires_at = now + expires_in
    nonce = secrets.token_hex(8)

    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": expires_at,
        "nonce": nonce,
    }

    payload_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")

    signature = hmac.new(SECRET_KEY.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")

    return f"{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and cryptographically verifies an access token."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)

        rem = len(payload_b64) % 4
        if rem:
            payload_b64 += "=" * (4 - rem)
        rem = len(sig_b64) % 4
        if rem:
            sig_b64 += "=" * (4 - rem)

        payload_bytes = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b64.encode("utf-8"))

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("Token verification failed: signature mismatch")
            return None

        payload = json.loads(payload_bytes.decode("utf-8"))
        now = int(time.time())

        if payload.get("exp", 0) < now:
            logger.warning("Token verification failed: token expired")
            return None

        return payload
    except Exception as e:
        logger.warning(f"Error parsing token: {e}")
        return None


def get_current_active_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db)
) -> models.User:
    """
    FastAPI dependency that enforces a valid Bearer token on protected endpoints.
    In testing/local dev without token, permits fallback to first active user if DB has users.
    """
    if credentials and credentials.scheme.lower() == "bearer":
        token = credentials.credentials
        payload = decode_access_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid, forged, or expired authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = db.query(models.User).filter(models.User.id == payload.get("sub")).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # If no token provided:
    # In test/dev environments without header, allow fallback to active user or create default dev employee
    env = os.getenv("ENV", "development")
    if env != "production":
        user = db.query(models.User).filter(models.User.is_active == True).first()
        if not user:
            user = models.User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="ADMIN",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login")
def login(
    username: str = Body(..., embed=True),
    password: str = Body(..., embed=True),
    db: Session = Depends(get_db)
):
    # Find user
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # Auto-seed initial admin if no users exist
    if not user and db.query(models.User).count() == 0:
        if username == "admin" and password == "admin123":
            user = models.User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="ADMIN",
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Audit log login
    audit = models.AuditLog(
        user_id=user.id,
        action="USER_LOGIN",
        entity_type="USER",
        entity_id=user.username,
        metadata_json={"role": user.role}
    )
    db.add(audit)
    db.commit()

    token = create_access_token(user.id, user.username, user.role)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_SECONDS,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    }


@router.get("/me")
def get_current_user_profile(
    current_user: models.User = Depends(get_current_active_user)
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role
    }


@router.post("/logout")
def logout(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    audit = models.AuditLog(
        user_id=current_user.id,
        action="USER_LOGOUT",
        entity_type="USER",
        entity_id=current_user.username,
        metadata_json={}
    )
    db.add(audit)
    db.commit()
    return {"message": "Logged out successfully"}
