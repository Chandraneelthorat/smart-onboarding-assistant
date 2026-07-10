"""JWT helpers for portal login (HR / Employee)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

ALGORITHM = "HS256"


def _secret() -> str:
    s = os.getenv("JWT_SECRET") or os.getenv("HR_JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET (or HR_JWT_SECRET) must be set for portal auth")
    return s


def create_access_token(
    *,
    role: str,
    employee_id: Optional[str],
    portal_user_id: int,
    expires_hours: int = 24,
) -> str:
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub": str(portal_user_id),
        "role": role,
        "emp_id": employee_id,
        "puid": portal_user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
