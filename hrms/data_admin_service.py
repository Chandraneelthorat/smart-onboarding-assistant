"""
HR data listings and mutations shared by /api/data routes and AI tools (HR role).
Raises LookupError for missing rows, ValueError for invalid input.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from emails import EmailSender
from hrms import ticket_notifications
from hrms.ticket_manager import apply_closure_notice_for_status
from models import (
    EmailLog,
    Employee,
    LeaveBalance,
    LeaveHistory,
    LeaveRequest,
    Manager,
    Meeting,
    PortalUser,
    Ticket,
)


def _parse_dt(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


# --- Employees ---


def list_employees(db: Session) -> Dict[str, Any]:
    rows = db.query(Employee).order_by(Employee.emp_id).all()
    return {
        "employees": [
            {
                "emp_id": e.emp_id,
                "name": e.name,
                "manager_id": e.manager_id,
                "email": e.email,
            }
            for e in rows
        ]
    }


def update_employee(db: Session, emp_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    emp = db.query(Employee).filter(Employee.emp_id == emp_id).first()
    if not emp:
        raise LookupError("Employee not found")
    if "name" in updates:
        n = (updates["name"] or "").strip()
        if not n:
            raise ValueError("Name cannot be empty")
        emp.name = n
    if "email" in updates:
        raw_e = updates["email"]
        emp.email = str(raw_e).strip() if raw_e is not None and str(raw_e).strip() else None
    if "manager_id" in updates:
        raw_m = updates["manager_id"]
        mid = str(raw_m).strip() if raw_m is not None and str(raw_m).strip() else None
        if mid:
            mgr = db.query(Employee).filter(Employee.emp_id == mid).first()
            if not mgr:
                raise ValueError("Manager not found")
        emp.manager_id = mid
    db.commit()
    db.refresh(emp)
    return {
        "emp_id": emp.emp_id,
        "name": emp.name,
        "manager_id": emp.manager_id,
        "email": emp.email,
    }


def delete_employee(db: Session, emp_id: str) -> Dict[str, str]:
    emp = db.query(Employee).filter(Employee.emp_id == emp_id).first()
    if not emp:
        raise LookupError("Employee not found")

    db.query(Employee).filter(Employee.manager_id == emp_id).update(
        {Employee.manager_id: None}, synchronize_session=False
    )
    db.query(Manager).filter(Manager.linked_emp_id == emp_id).update(
        {Manager.linked_emp_id: None},
        synchronize_session=False,
    )
    db.query(LeaveRequest).filter(LeaveRequest.approved_by_emp_id == emp_id).update(
        {LeaveRequest.approved_by_emp_id: None},
        synchronize_session=False,
    )
    db.query(LeaveRequest).filter(LeaveRequest.emp_id == emp_id).delete(synchronize_session=False)
    db.query(LeaveHistory).filter(LeaveHistory.emp_id == emp_id).delete(synchronize_session=False)
    db.query(Meeting).filter(Meeting.hr_emp_id == emp_id).update(
        {Meeting.hr_emp_id: None},
        synchronize_session=False,
    )
    db.query(Meeting).filter(Meeting.emp_id == emp_id).delete(synchronize_session=False)
    db.query(Ticket).filter(Ticket.emp_id == emp_id).delete(synchronize_session=False)
    db.query(LeaveBalance).filter(LeaveBalance.emp_id == emp_id).delete(synchronize_session=False)
    db.query(EmailLog).filter(EmailLog.emp_id == emp_id).delete(synchronize_session=False)
    db.query(PortalUser).filter(PortalUser.employee_id == emp_id).delete(synchronize_session=False)
    db.delete(emp)
    db.commit()
    return {"message": f"Employee {emp_id} and related rows deleted."}


# --- Leave balances ---


def list_leave_balances(db: Session) -> Dict[str, Any]:
    rows = db.query(LeaveBalance).order_by(LeaveBalance.emp_id).all()
    return {
        "leave_balances": [
            {"id": r.id, "emp_id": r.emp_id, "balance": r.balance} for r in rows
        ]
    }


def set_leave_balance(db: Session, emp_id: str, balance: int) -> Dict[str, Any]:
    rec = db.query(LeaveBalance).filter(LeaveBalance.emp_id == emp_id).first()
    if not rec:
        raise LookupError("Leave balance row not found")
    rec.balance = balance
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "emp_id": rec.emp_id, "balance": rec.balance}


# --- Leave history ---


def list_leave_history(
    db: Session, emp_id: Optional[str] = None, limit: int = 500
) -> Dict[str, Any]:
    q = db.query(LeaveHistory).order_by(LeaveHistory.id)
    if emp_id:
        q = q.filter(LeaveHistory.emp_id == emp_id)
    rows = q.limit(limit).all()
    return {
        "leave_history": [
            {
                "id": r.id,
                "emp_id": r.emp_id,
                "leave_date": r.leave_date.isoformat(),
                "request_id": r.request_id,
            }
            for r in rows
        ]
    }


def create_leave_history(
    db: Session, emp_id: str, leave_date: str, request_id: int
) -> Dict[str, Any]:
    if not db.query(Employee).filter(Employee.emp_id == emp_id).first():
        raise ValueError("Employee not found")
    try:
        ld = date.fromisoformat(leave_date)
    except ValueError as e:
        raise ValueError("Invalid leave_date (use YYYY-MM-DD)") from e
    row = LeaveHistory(
        emp_id=emp_id,
        leave_date=ld,
        request_id=request_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "emp_id": row.emp_id,
        "leave_date": row.leave_date.isoformat(),
        "request_id": row.request_id,
    }


def delete_leave_history(db: Session, row_id: int) -> Dict[str, str]:
    row = db.query(LeaveHistory).filter(LeaveHistory.id == row_id).first()
    if not row:
        raise LookupError("Row not found")
    db.delete(row)
    db.commit()
    return {"message": f"Leave history row {row_id} deleted."}


# --- Meetings ---


def list_meetings(db: Session, emp_id: Optional[str] = None) -> Dict[str, Any]:
    q = db.query(Meeting).order_by(Meeting.meeting_dt)
    if emp_id:
        q = q.filter(Meeting.emp_id == emp_id)
    rows = q.all()
    return {
        "meetings": [
            {
                "id": m.id,
                "emp_id": m.emp_id,
                "meeting_dt": m.meeting_dt.isoformat(),
                "topic": m.topic,
            }
            for m in rows
        ]
    }


def update_meeting(
    db: Session,
    meeting_id: int,
    *,
    emp_id: Optional[str] = None,
    meeting_dt: Optional[str] = None,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise LookupError("Meeting not found")
    if emp_id is not None:
        if not db.query(Employee).filter(Employee.emp_id == emp_id).first():
            raise ValueError("Employee not found")
        m.emp_id = emp_id
    if meeting_dt is not None:
        m.meeting_dt = _parse_dt(meeting_dt)
    if topic is not None:
        m.topic = topic
    db.commit()
    db.refresh(m)
    return {
        "id": m.id,
        "emp_id": m.emp_id,
        "meeting_dt": m.meeting_dt.isoformat(),
        "topic": m.topic,
    }


def delete_meeting(db: Session, meeting_id: int) -> Dict[str, str]:
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise LookupError("Meeting not found")
    db.delete(m)
    db.commit()
    return {"message": f"Meeting {meeting_id} deleted."}


# --- Tickets ---


def list_all_tickets(db: Session) -> Dict[str, Any]:
    rows = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return {
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "emp_id": t.emp_id,
                "item": t.item,
                "reason": t.reason,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in rows
        ]
    }


def patch_ticket_full(
    db: Session,
    ticket_id: str,
    *,
    item: Optional[str] = None,
    reason: Optional[str] = None,
    status: Optional[str] = None,
    emailer: Optional[EmailSender] = None,
) -> Dict[str, Any]:
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        raise LookupError("Ticket not found")
    old_status = t.status
    if item is not None:
        t.item = item
    if reason is not None:
        t.reason = reason
    if status is not None:
        t.status = status
        apply_closure_notice_for_status(t, status)
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(t)
    if (
        emailer is not None
        and status is not None
        and status == "Closed"
        and old_status != "Closed"
    ):
        ticket_notifications.notify_employee_ticket_resolved(db, emailer, t)
    return {
        "ticket_id": t.ticket_id,
        "emp_id": t.emp_id,
        "item": t.item,
        "reason": t.reason,
        "status": t.status,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


def delete_ticket(db: Session, ticket_id: str) -> Dict[str, str]:
    t = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not t:
        raise LookupError("Ticket not found")
    db.delete(t)
    db.commit()
    return {"message": f"Ticket {ticket_id} deleted."}


# --- Email logs ---


def list_email_logs(
    db: Session,
    emp_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    q = db.query(EmailLog)
    if emp_id:
        q = q.filter(EmailLog.emp_id == emp_id)
    total = q.count()
    rows = q.order_by(EmailLog.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "email_logs": [
            {
                "id": r.id,
                "emp_id": r.emp_id,
                "to_addresses": r.to_addresses,
                "subject": r.subject,
                "body": r.body,
                "is_html": r.is_html,
                "purpose": r.purpose,
                "delivery_status": r.delivery_status,
                "error_detail": r.error_detail,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


def delete_email_log(db: Session, log_id: int) -> Dict[str, str]:
    row = db.query(EmailLog).filter(EmailLog.id == log_id).first()
    if not row:
        raise LookupError("Log not found")
    db.delete(row)
    db.commit()
    return {"message": f"Email log {log_id} deleted."}


# --- People-manager roster (mgr_id M…, separate from employees.emp_id E…) ---


def list_managers_roster(db: Session) -> Dict[str, Any]:
    rows = db.query(Manager).order_by(Manager.mgr_id).all()
    return {
        "managers": [
            {
                "mgr_id": m.mgr_id,
                "name": m.name,
                "email": m.email,
                "linked_emp_id": m.linked_emp_id,
                "onboarding_status": m.onboarding_status or "Active",
            }
            for m in rows
        ]
    }


def update_manager(db: Session, mgr_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    row = db.query(Manager).filter(Manager.mgr_id == mgr_id).first()
    if not row:
        raise LookupError("Manager not found")
    if "name" in updates and updates["name"] is not None:
        n = str(updates["name"]).strip()
        if not n:
            raise ValueError("Name cannot be empty")
        row.name = n
    if "email" in updates:
        raw = updates["email"]
        row.email = str(raw).strip() if raw is not None and str(raw).strip() else None
    if "linked_emp_id" in updates:
        raw = updates["linked_emp_id"]
        if raw is None or (isinstance(raw, str) and not str(raw).strip()):
            row.linked_emp_id = None
        else:
            eid = str(raw).strip()
            if not db.query(Employee).filter(Employee.emp_id == eid).first():
                raise ValueError(f"Employee '{eid}' not found")
            row.linked_emp_id = eid
    if "onboarding_status" in updates and updates["onboarding_status"] is not None:
        s = str(updates["onboarding_status"]).strip()
        if s:
            row.onboarding_status = s
    db.commit()
    db.refresh(row)
    return {
        "mgr_id": row.mgr_id,
        "name": row.name,
        "email": row.email,
        "linked_emp_id": row.linked_emp_id,
        "onboarding_status": row.onboarding_status or "Active",
    }


def delete_manager(db: Session, mgr_id: str) -> Dict[str, str]:
    row = db.query(Manager).filter(Manager.mgr_id == mgr_id).first()
    if not row:
        raise LookupError("Manager not found")
    db.delete(row)
    db.commit()
    return {"message": f"Manager roster row {mgr_id} deleted."}
