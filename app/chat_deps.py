"""Resolve ChatContext from X-API-Key or Bearer JWT."""
from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from app.auth import get_shared_api_key
from app.auth_jwt import decode_access_token
from app.chat_context import ChatContext


def get_chat_context(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> ChatContext:
    expected = get_shared_api_key()

    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        try:
            payload = decode_access_token(token)
        except Exception as exc:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
            ) from exc
        raw = str(payload.get("role", "employee")).strip().lower()
        role = raw if raw in ("hr", "employee") else "employee"
        emp_id = payload.get("emp_id")
        if isinstance(emp_id, str) and not emp_id.strip():
            emp_id = None
        puid = payload.get("puid")
        return ChatContext(
            role=role,
            portal_user_id=int(puid) if puid is not None else None,
            employee_id=emp_id,
            approver_emp_id=emp_id if role == "hr" else None,
        )

    if expected and x_api_key == expected:
        return ChatContext(role="hr")

    if not expected:
        return ChatContext(role="hr")

    raise HTTPException(
        status_code=401,
        detail="Send X-API-Key or Authorization: Bearer <JWT>",
    )
