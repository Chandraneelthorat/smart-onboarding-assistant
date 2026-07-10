"""JWT-only dashboard data for HR / Employee (no X-API-Key)."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from emails import EmailSender
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db, get_emailer
from app.auth_jwt import decode_access_token
from app.schemas import MessageResponse
from hrms import tools_impl as ti

router = APIRouter(prefix="/portal", tags=["portal"])


def _bearer_payload(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        return decode_access_token(authorization[7:].strip())
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def _require_hr(p: Dict[str, Any]) -> None:
    if str(p.get("role") or "").strip().lower() != "hr":
        raise HTTPException(status_code=403, detail="HR role required")


def _resolve_approver_emp_id(p: Dict[str, Any]) -> Optional[str]:
    """
    Prefer the HR portal user's linked employee id, then HR_APPROVER_EMP_ID.
    If neither is set, approvals still succeed; approved_by_emp_id is stored as null.
    """
    raw = p.get("emp_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    env = (os.getenv("HR_APPROVER_EMP_ID") or "").strip()
    return env or None


@router.get("/summary")
def portal_summary(
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> Dict[str, Any]:
    raw_role = str(p.get("role", "employee")).strip().lower()
    role = raw_role if raw_role in ("hr", "employee") else "employee"
    emp_id = p.get("emp_id")
    if isinstance(emp_id, str) and not emp_id.strip():
        emp_id = None

    if role == "employee":
        if not emp_id:
            raise HTTPException(status_code=400, detail="Employee login has no linked employee_id")
        return {
            "role": role,
            "employee": ti.get_employee_by_id_impl(db, emp_id),
            "tickets": ti.list_tickets_impl(db, employee_id=emp_id),
            "closed_ticket_alerts": ti.list_pending_closure_notices_impl(db, emp_id),
            "meetings": ti.get_meetings_impl(db, emp_id),
            "leave_balance": ti.get_employee_leave_balance_impl(db, emp_id),
            "leave_history_text": ti.get_leave_history_impl(db, emp_id),
            "leave_requests": ti.list_leave_requests_impl(db, emp_id=emp_id),
        }

    if role == "hr":
        emp_profile = None
        if emp_id:
            try:
                emp_profile = ti.get_employee_by_id_impl(db, emp_id)
            except ValueError:
                emp_profile = None
        all_tickets = ti.list_tickets_impl(db)
        recent_tickets = sorted(
            all_tickets,
            key=lambda r: str(r.get("created_at") or ""),
            reverse=True,
        )[:50]
        return {
            "role": role,
            "employee": emp_profile,
            "pending_leave_requests": ti.list_leave_requests_impl(db, status="Pending"),
            "recent_tickets": recent_tickets,
        }

    raise HTTPException(status_code=403, detail="Unsupported role")


@router.get("/hr/recent-tickets")
def portal_hr_recent_tickets(
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> Dict[str, Any]:
    """JWT-only ticket list for the HR Tickets tab (same shape as summary.recent_tickets)."""
    _require_hr(p)
    all_tickets = ti.list_tickets_impl(db)
    recent_tickets = sorted(
        all_tickets,
        key=lambda r: str(r.get("created_at") or ""),
        reverse=True,
    )[:50]
    return {"recent_tickets": recent_tickets}


class PortalLeaveBody(BaseModel):
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=1)
    message: Optional[str] = None


@router.post("/leave/request", response_model=MessageResponse)
def portal_submit_leave(
    body: PortalLeaveBody,
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    if str(p.get("role") or "").strip().lower() != "employee":
        raise HTTPException(status_code=403, detail="Only employees may use this endpoint")
    emp_id = p.get("emp_id")
    if not emp_id:
        raise HTTPException(status_code=400, detail="No employee_id on token")
    try:
        msg = ti.submit_leave_request_impl(
            db,
            emp_id,
            body.start_date,
            body.end_date,
            body.reason,
            body.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=msg)


class PortalTicketBody(BaseModel):
    item: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    title: Optional[str] = None


class AckClosureNoticesBody(BaseModel):
    """If ticket_ids is empty, all pending closure notices for this employee are cleared."""

    ticket_ids: Optional[List[str]] = None


@router.post("/tickets", response_model=MessageResponse)
def portal_employee_create_ticket(
    body: PortalTicketBody,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    if str(p.get("role") or "").strip().lower() != "employee":
        raise HTTPException(status_code=403, detail="Only employees may use this endpoint")
    emp_id = p.get("emp_id")
    if not emp_id or not str(emp_id).strip():
        raise HTTPException(status_code=400, detail="No employee_id on token")
    emp_id = str(emp_id).strip()
    try:
        msg = ti.create_ticket_impl(
            db,
            emp_id,
            body.item.strip(),
            body.reason.strip(),
            title=body.title.strip() if body.title and body.title.strip() else None,
            department="IT",
            created_by_emp_id=emp_id,
            emailer=emailer,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=msg)


@router.post("/tickets/closure-notices/ack", response_model=MessageResponse)
def portal_ack_closure_notices(
    body: AckClosureNoticesBody,
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    if str(p.get("role") or "").strip().lower() != "employee":
        raise HTTPException(status_code=403, detail="Only employees may use this endpoint")
    emp_raw = p.get("emp_id")
    if not emp_raw or not str(emp_raw).strip():
        raise HTTPException(status_code=400, detail="No employee_id on token")
    emp_id = str(emp_raw).strip()
    ids = body.ticket_ids if body.ticket_ids else None
    msg = ti.acknowledge_closure_notices_impl(db, emp_id, ids)
    return MessageResponse(message=msg)


class PortalHrLeaveForBody(BaseModel):
    emp_id: str = Field(..., min_length=1)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=1)
    message: Optional[str] = None


@router.post("/leave/hr-submit-for", response_model=MessageResponse)
def portal_hr_submit_leave_for_employee(
    body: PortalHrLeaveForBody,
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    _require_hr(p)
    try:
        msg = ti.submit_leave_request_impl(
            db,
            body.emp_id.strip(),
            body.start_date,
            body.end_date,
            body.reason,
            body.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=msg)


@router.post("/leave/requests/{request_id}/approve", response_model=MessageResponse)
def portal_approve_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    _require_hr(p)
    approver = _resolve_approver_emp_id(p)
    try:
        msg = ti.approve_leave_request_impl(db, request_id, approver)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=msg)


@router.post("/leave/requests/{request_id}/reject", response_model=MessageResponse)
def portal_reject_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    p: Dict[str, Any] = Depends(_bearer_payload),
) -> MessageResponse:
    _require_hr(p)
    approver = _resolve_approver_emp_id(p)
    try:
        msg = ti.reject_leave_request_impl(db, request_id, approver)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=msg)
