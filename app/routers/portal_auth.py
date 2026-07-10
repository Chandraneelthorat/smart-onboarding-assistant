"""Portal login (JWT) for HR and Employee dashboards."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_jwt import create_access_token
from app.deps import get_db
from app.passwords import verify_password
from models import PortalUser

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    employee_id: Optional[str] = None


@router.post("/login", response_model=TokenOut)
def login(body: LoginBody, db: Session = Depends(get_db)) -> TokenOut:
    if not os.getenv("JWT_SECRET") and not os.getenv("HR_JWT_SECRET"):
        raise HTTPException(
            status_code=503,
            detail="JWT_SECRET is not configured on the server",
        )
    row = db.query(PortalUser).filter(PortalUser.email == body.email.strip().lower()).first()
    if not row or not row.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, row.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(
        role=row.role,
        employee_id=row.employee_id,
        portal_user_id=row.id,
    )
    return TokenOut(
        access_token=token,
        role=row.role,
        employee_id=row.employee_id,
    )
