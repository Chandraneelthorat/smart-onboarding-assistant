"""
Full CRUD HTTP API for HR data tables (employees, leave, meetings, tickets, email_logs).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from emails import EmailSender
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.deps import get_db, get_emailer
from app.schemas_data import (
    EmployeePatchBody,
    LeaveBalancePatchBody,
    LeaveHistoryCreateBody,
    ManagerPatchBody,
    MeetingCreateDataBody,
    MeetingPatchBody,
    TicketFullPatchBody,
)
from hrms import data_admin_service as das
from hrms import tools_impl as ti

router = APIRouter(prefix="/data", dependencies=[Depends(verify_api_key)])


# --- Employees ---


@router.get("/employees")
def list_employees(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return das.list_employees(db)


@router.get("/managers")
def list_managers_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Full people-manager roster (M-prefixed ids), separate from HRMS employees."""
    return das.list_managers_roster(db)


@router.patch("/managers/{mgr_id}")
def patch_manager(
    mgr_id: str,
    body: ManagerPatchBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return das.update_manager(db, mgr_id, body.model_dump(exclude_unset=True))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/managers/{mgr_id}")
def delete_manager_row(mgr_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_manager(db, mgr_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/onboarding-managers")
def list_onboarding_managers(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Subset of the manager roster: only rows with linked_emp_id (for onboarding reporting-line pickers).
    """
    full = das.list_managers_roster(db)["managers"]
    linked = [m for m in full if m.get("linked_emp_id")]
    linked.sort(key=lambda x: (x.get("name") or "", x.get("mgr_id") or ""))
    return {
        "managers": [
            {
                "mgr_id": m["mgr_id"],
                "name": m["name"],
                "email": m["email"],
                "linked_emp_id": m["linked_emp_id"],
            }
            for m in linked
        ]
    }


@router.patch("/employees/{emp_id}")
def patch_employee(
    emp_id: str,
    body: EmployeePatchBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return das.update_employee(db, emp_id, body.model_dump(exclude_unset=True))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/employees/{emp_id}")
def delete_employee(emp_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_employee(db, emp_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Leave balances ---


@router.get("/leave-balances")
def list_leave_balances(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return das.list_leave_balances(db)


@router.patch("/leave-balances/{emp_id}")
def patch_leave_balance(
    emp_id: str,
    body: LeaveBalancePatchBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return das.set_leave_balance(db, emp_id, body.balance)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Leave history ---


@router.get("/leave-history")
def list_leave_history(
    emp_id: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return das.list_leave_history(db, emp_id=emp_id, limit=limit)


@router.post("/leave-history")
def create_leave_history(
    body: LeaveHistoryCreateBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return das.create_leave_history(db, body.emp_id, body.leave_date, body.request_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/leave-history/{row_id}")
def delete_leave_history(row_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_leave_history(db, row_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Meetings ---


@router.post("/meetings")
def create_meeting_data(
    body: MeetingCreateDataBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        msg = ti.schedule_meeting_impl(
            db, body.emp_id, body.meeting_datetime, body.topic
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": msg}


@router.get("/meetings")
def list_meetings_data(
    emp_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return das.list_meetings(db, emp_id=emp_id)


@router.patch("/meetings/{meeting_id}")
def patch_meeting(
    meeting_id: int,
    body: MeetingPatchBody,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        return das.update_meeting(
            db,
            meeting_id,
            emp_id=body.emp_id,
            meeting_dt=body.meeting_dt,
            topic=body.topic,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_meeting(db, meeting_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Tickets ---


@router.get("/tickets-all")
def list_all_tickets(db: Session = Depends(get_db)) -> Dict[str, Any]:
    return das.list_all_tickets(db)


@router.patch("/tickets/{ticket_id}/full")
def patch_ticket_full(
    ticket_id: str,
    body: TicketFullPatchBody,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
) -> Dict[str, Any]:
    try:
        return das.patch_ticket_full(
            db,
            ticket_id,
            item=body.item,
            reason=body.reason,
            status=body.status,
            emailer=emailer,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/tickets/{ticket_id}")
def delete_ticket(ticket_id: str, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_ticket(db, ticket_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# --- Email logs ---


@router.get("/email-logs")
def list_email_logs(
    emp_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    return das.list_email_logs(db, emp_id=emp_id, limit=limit, offset=offset)


@router.delete("/email-logs/{log_id}")
def delete_email_log(log_id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        return das.delete_email_log(db, log_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
