"""Leave request workflow: submit → pending → approve/reject with balance deduction on approve."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import Employee, LeaveBalance, LeaveHistory, LeaveRequest


def _inclusive_days(start: date, end: date) -> int:
    return (end - start).days + 1


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def submit_leave_request(
    db: Session,
    emp_id: str,
    start_date: date,
    end_date: date,
    reason: str,
    message: Optional[str] = None,
) -> str:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")
    if not db.query(Employee).filter(Employee.emp_id == emp_id).first():
        raise ValueError(f"Employee '{emp_id}' not found.")
    n = _inclusive_days(start_date, end_date)
    row = LeaveRequest(
        emp_id=emp_id,
        start_date=start_date,
        end_date=end_date,
        number_of_days=n,
        reason=reason,
        message=message,
        status="Pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return (
        f"Leave request #{row.id} submitted for {emp_id}: {start_date} to {end_date} "
        f"({n} day(s)). Status: Pending HR approval."
    )


def list_leave_requests(
    db: Session,
    emp_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    q = (
        db.query(LeaveRequest, Employee.name)
        .outerjoin(Employee, LeaveRequest.emp_id == Employee.emp_id)
        .order_by(LeaveRequest.created_at.desc())
    )
    if emp_id:
        q = q.filter(LeaveRequest.emp_id == emp_id)
    if status:
        q = q.filter(LeaveRequest.status.ilike(status))
    rows = q.limit(200).all()
    return [
        {
            "leave_id": r.id,
            "employee_id": r.emp_id,
            "employee_name": (name or "").strip() if name else "",
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "number_of_days": r.number_of_days,
            "reason": r.reason,
            "message": r.message,
            "status": r.status,
            "approved_by": r.approved_by_emp_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r, name in rows
    ]


def approve_leave_request(
    db: Session,
    request_id: int,
    approver_emp_id: Optional[str] = None,
) -> str:
    if approver_emp_id is not None and not str(approver_emp_id).strip():
        approver_emp_id = None
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        raise ValueError(f"Leave request #{request_id} not found.")
    if req.status != "Pending":
        raise ValueError(f"Request is not pending (status={req.status}).")

    bal = db.query(LeaveBalance).filter(LeaveBalance.emp_id == req.emp_id).first()
    if not bal:
        raise ValueError("No leave balance record for employee.")
    if bal.balance < req.number_of_days:
        raise ValueError(
            f"Insufficient balance: need {req.number_of_days}, have {bal.balance}."
        )

    max_request = (
        db.query(LeaveHistory)
        .filter(LeaveHistory.emp_id == req.emp_id)
        .order_by(LeaveHistory.request_id.desc())
        .first()
    )
    next_rid = (max_request.request_id + 1) if max_request else 1

    bal.balance -= req.number_of_days
    for d in _daterange(req.start_date, req.end_date):
        db.add(
            LeaveHistory(
                emp_id=req.emp_id,
                leave_date=d,
                request_id=next_rid,
            )
        )

    req.status = "Approved"
    req.approved_by_emp_id = approver_emp_id
    req.updated_at = datetime.now(timezone.utc)
    db.commit()
    return (
        f"Leave request #{request_id} approved. Deducted {req.number_of_days} day(s). "
        f"Remaining balance: {bal.balance}."
    )


def reject_leave_request(
    db: Session,
    request_id: int,
    approver_emp_id: Optional[str] = None,
) -> str:
    if approver_emp_id is not None and not str(approver_emp_id).strip():
        approver_emp_id = None
    req = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
    if not req:
        raise ValueError(f"Leave request #{request_id} not found.")
    if req.status != "Pending":
        raise ValueError(f"Request is not pending (status={req.status}).")
    req.status = "Rejected"
    req.approved_by_emp_id = approver_emp_id
    req.updated_at = datetime.now(timezone.utc)
    db.commit()
    return f"Leave request #{request_id} rejected."
