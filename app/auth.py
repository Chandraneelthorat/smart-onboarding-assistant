import os
from typing import Optional

from fastapi import Header, HTTPException, status

from app.auth_jwt import decode_access_token


def get_shared_api_key() -> Optional[str]:
    """
    Single application API key used for both HR and Employee API clients.
    Set API_KEY in the environment; HR_API_KEY is accepted as a legacy alias.
    """
    return os.getenv("API_KEY") or os.getenv("HR_API_KEY")


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
) -> None:
    """
    Protect /api routes. Accepts:
    - X-API-Key matching API_KEY (or legacy HR_API_KEY)
    - Bearer JWT with role=hr (same header used by the SPA after login)
    If no API key is configured, all /api routes are open (local dev only).
    """
    expected = get_shared_api_key()
    if expected and x_api_key == expected:
        return
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = decode_access_token(authorization[7:].strip())
            if str(payload.get("role") or "").strip().lower() == "hr":
                return
        except Exception:
            pass
    if not expected:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key (or HR Bearer token)",
    )
