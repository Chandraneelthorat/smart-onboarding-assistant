"""
Shared HR tool logic used by MCP (server.py) and HTTP API / OpenRouter dispatch.
"""
from __future__ import annotations

import json
import secrets
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from emails import EmailSender
from hrms import (
    EmployeeManager,
    LeaveManager,
    MeetingManager,
    TicketManager,
)
from hrms.data_admin_service import list_managers_roster
from hrms.leave_request_service import (
    approve_leave_request,
    list_leave_requests,
    reject_leave_request,
    submit_leave_request,
)
from hrms import ticket_notifications
from hrms.schemas import (
    EmployeeCreate,
    LeaveApplyRequest,
    MeetingCancelRequest,
    MeetingCreate,
    TicketCreate,
    TicketStatusUpdate,
)
from models import PortalUser, Ticket


def _provision_employee_portal_account(
    db: Session,
    emp_id: str,
    email: str,
    initial_password: Optional[str] = None,
) -> tuple[str, bool]:
    """
    Create or reset an employee portal login (username = email).
    Returns (plain_password, was_existing_reset).
    """
    from app.passwords import hash_password

    email_norm = email.strip().lower()
    if not email_norm:
        raise ValueError("Email is required to create a portal login.")

    raw_pw = (initial_password or "").strip()
    pw = raw_pw if raw_pw else secrets.token_urlsafe(14)
    if len(pw) < 8:
        raise ValueError("If you set initial_password, it must be at least 8 characters.")

    existing = db.query(PortalUser).filter(PortalUser.email == email_norm).first()
    if existing:
        if existing.employee_id != emp_id:
            raise ValueError(
                "This email is already used by another portal account "
                f"(employee {existing.employee_id})."
            )
        existing.password_hash = hash_password(pw)
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return pw, True

    row = PortalUser(
        email=email_norm,
        password_hash=hash_password(pw),
        role="employee",
        employee_id=emp_id,
        is_active=True,
    )
    db.add(row)
    db.commit()
    return pw, False


def parse_meeting_datetime(meeting_datetime: str) -> datetime:
    try:
        return datetime.fromisoformat(meeting_datetime)
    except ValueError:
        return datetime.strptime(meeting_datetime, "%Y-%m-%d %H:%M:%S")


def add_employee_impl(
    db: Session,
    emp_name: str,
    email: Optional[str] = None,
    manager_id: Optional[str] = None,
    *,
    create_portal_login: bool = False,
    initial_password: Optional[str] = None,
) -> str:
    from hrms.atom_email import ensure_atom_work_email

    email = ensure_atom_work_email(emp_name, email)
    em = EmployeeManager(db)
    emp = EmployeeCreate(
        emp_id=em.get_next_emp_id(),
        name=emp_name,
        manager_id=manager_id if manager_id else None,
        email=email,
    )
    em.add_employee(emp)
    msg = (
        f"Employee '{emp_name}' added successfully. Employee ID: {emp.emp_id}."
    )
    if create_portal_login:
        try:
            pw, updated = _provision_employee_portal_account(
                db, emp.emp_id, email, initial_password
            )
            msg += (
                f" Portal login — username (email): {email.strip().lower()}. "
                f"Temporary password: {pw}. "
            )
            if updated:
                msg += "Existing portal account for this email was reset with the new password."
            else:
                msg += "Share credentials securely with the employee; they should sign in and change the password if your policy requires it."
        except ValueError as e:
            msg += f" Portal login was not created: {e}"
    return msg


def add_employee_get_id(
    db: Session,
    emp_name: str,
    email: Optional[str] = None,
    manager_id: Optional[str] = None,
    *,
    create_portal_login: bool = False,
    initial_password: Optional[str] = None,
) -> tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    Create employee row. Optionally provision portal login (username = work email).

    Returns ``(emp_id, portal_username, portal_plain_password, portal_error)``.
    When ``create_portal_login`` is false, portal fields are ``None``.
    On provisioning failure, ``portal_error`` is set and password is ``None``.
    """
    from hrms.atom_email import ensure_atom_work_email

    email = ensure_atom_work_email(emp_name, email)
    em = EmployeeManager(db)
    emp = EmployeeCreate(
        emp_id=em.get_next_emp_id(),
        name=emp_name,
        manager_id=manager_id if manager_id else None,
        email=email,
    )
    em.add_employee(emp)
    if not create_portal_login:
        return emp.emp_id, None, None, None
    try:
        pw, _ = _provision_employee_portal_account(
            db, emp.emp_id, email, initial_password
        )
        return emp.emp_id, email.strip().lower(), pw, None
    except ValueError as e:
        return emp.emp_id, None, None, str(e)


def find_employee_by_name_impl(db: Session, name: str) -> Dict[str, str]:
    em = EmployeeManager(db)
    matches = em.search_employee_by_name(name)
    if not matches:
        raise ValueError(f"No employees found matching '{name}'.")
    return em.get_employee_details(matches[0])


def list_managers_impl(db: Session) -> List[Dict[str, Any]]:
    """All people-manager roster rows (M-prefixed mgr_id), separate from HRMS employees."""
    return list_managers_roster(db)["managers"]


def get_employee_by_id_impl(db: Session, emp_id: str) -> Dict[str, Any]:
    em = EmployeeManager(db)
    return em.get_employee_details(emp_id)


def send_email_impl(
    emailer: EmailSender,
    to_emails: List[str],
    subject: str,
    body: str,
    html: bool = False,
) -> str:
    emailer.send_email(subject, body, to_emails, from_email=emailer.username, html=html)
    return "Email sent successfully."


def create_ticket_impl(
    db: Session,
    emp_id: str,
    item: str,
    reason: str,
    *,
    title: Optional[str] = None,
    department: Optional[str] = None,
    created_by_emp_id: Optional[str] = None,
    emailer: Optional[EmailSender] = None,
) -> str:
    tm = TicketManager(db)
    ticket_req = TicketCreate(
        emp_id=emp_id,
        item=item,
        reason=reason,
        title=title,
        department=department,
        created_by_emp_id=created_by_emp_id,
    )
    ticket_id = tm.create_ticket(ticket_req)
    if emailer:
        row = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if row:
            ticket_notifications.notify_employee_new_ticket(db, emailer, row)
    return f"Ticket {ticket_id} created for {emp_id}."


def update_ticket_status_impl(
    db: Session,
    ticket_id: str,
    status: str,
    *,
    emailer: Optional[EmailSender] = None,
) -> str:
    tm = TicketManager(db)
    ticket_status_update = TicketStatusUpdate(status=status)  # type: ignore[arg-type]
    msg = tm.update_ticket_status(ticket_status_update, ticket_id)
    if emailer and status == "Closed":
        row = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if row:
            ticket_notifications.notify_employee_ticket_resolved(db, emailer, row)
    return msg


def list_tickets_impl(
    db: Session,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, str]]:
    tm = TicketManager(db)
    return tm.list_tickets(employee_id=employee_id, status=status)


def list_pending_closure_notices_impl(db: Session, emp_id: str) -> List[Dict[str, str]]:
    return TicketManager(db).list_pending_closure_notices(emp_id)


def acknowledge_closure_notices_impl(
    db: Session, emp_id: str, ticket_ids: Optional[List[str]] = None
) -> str:
    n = TicketManager(db).acknowledge_closure_notices(emp_id, ticket_ids)
    if n == 0:
        return "No pending notices to clear."
    return f"Cleared {n} notice(s)."


def schedule_meeting_impl(
    db: Session,
    employee_id: str,
    meeting_datetime: str,
    topic: str,
    *,
    hr_emp_id: Optional[str] = None,
    agenda: Optional[str] = None,
    location_or_link: Optional[str] = None,
    display_participant_id: Optional[str] = None,
) -> str:
    dt_obj = parse_meeting_datetime(meeting_datetime)
    mm = MeetingManager(db)
    meeting_req = MeetingCreate(
        emp_id=employee_id,
        meeting_dt=dt_obj,
        topic=topic,
        hr_emp_id=hr_emp_id,
        agenda=agenda,
        location_or_link=location_or_link,
        display_participant_id=display_participant_id,
    )
    return mm.schedule_meeting(meeting_req)


def get_meetings_impl(db: Session, employee_id: str) -> List[Dict[str, str]]:
    mm = MeetingManager(db)
    return mm.get_meetings(employee_id)


def cancel_meeting_impl(
    db: Session,
    employee_id: str,
    meeting_datetime: str,
    topic: Optional[str] = None,
) -> str:
    dt_obj = parse_meeting_datetime(meeting_datetime)
    mm = MeetingManager(db)
    meeting_req = MeetingCancelRequest(emp_id=employee_id, meeting_dt=dt_obj, topic=topic)
    return mm.cancel_meeting(meeting_req)


def get_employee_leave_balance_impl(db: Session, emp_id: str) -> str:
    lm = LeaveManager(db)
    return lm.get_leave_balance(emp_id)


def _normalize_leave_dates(leave_dates: List[Any]) -> List[date]:
    out: List[date] = []
    for d in leave_dates:
        if isinstance(d, date):
            out.append(d)
        else:
            out.append(date.fromisoformat(str(d)))
    return out


def apply_leave_impl(db: Session, emp_id: str, leave_dates: List[Any]) -> str:
    """Legacy: immediate deduct (admin-style). Prefer submit_leave_request for employees."""
    lm = LeaveManager(db)
    req = LeaveApplyRequest(emp_id=emp_id, leave_dates=_normalize_leave_dates(leave_dates))
    return lm.apply_leave(req)


def submit_leave_request_impl(
    db: Session,
    emp_id: str,
    start_date: str,
    end_date: str,
    reason: str,
    message: Optional[str] = None,
) -> str:
    sd = date.fromisoformat(start_date)
    ed = date.fromisoformat(end_date)
    return submit_leave_request(db, emp_id, sd, ed, reason, message)


def list_leave_requests_impl(
    db: Session,
    emp_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    return list_leave_requests(db, emp_id=emp_id, status=status)


def approve_leave_request_impl(
    db: Session, request_id: int, approver_emp_id: Optional[str] = None
) -> str:
    return approve_leave_request(db, request_id, approver_emp_id)


def reject_leave_request_impl(
    db: Session, request_id: int, approver_emp_id: Optional[str] = None
) -> str:
    return reject_leave_request(db, request_id, approver_emp_id)


def get_leave_history_impl(db: Session, emp_id: str) -> str:
    lm = LeaveManager(db)
    base = lm.get_leave_history(emp_id)
    pending = list_leave_requests(db, emp_id=emp_id)
    if not pending:
        return base
    lines = [base]
    lines.append("Leave requests (workflow):")
    for r in pending:
        lines.append(
            f"  #{r['leave_id']}: {r['start_date']}–{r['end_date']} "
            f"({r['number_of_days']}d) status={r['status']} reason={r['reason'][:80]}"
        )
    return "\n".join(lines)


def tool_result_to_json(result: Union[str, Dict, List]) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, default=str)


TOOL_NAMES = [
    "add_employee",
    "find_employee_by_name",
    "list_managers",
    "update_manager",
    "delete_manager",
    "get_employee_by_id",
    "send_email",
    "create_ticket",
    "update_ticket_status",
    "list_tickets",
    "schedule_meeting",
    "get_meetings",
    "cancel_meeting",
    "get_employee_leave_balance",
    "apply_leave",
    "submit_leave_request",
    "list_leave_requests",
    "approve_leave_request",
    "reject_leave_request",
    "get_leave_history",
    "list_employees",
    "update_employee",
    "delete_employee",
    "list_leave_balances",
    "set_leave_balance",
    "list_leave_history_records",
    "add_leave_history_record",
    "delete_leave_history_record",
    "list_all_meetings",
    "update_meeting",
    "delete_meeting_by_id",
    "list_all_tickets_admin",
    "update_ticket_fields",
    "delete_ticket",
    "list_email_logs",
    "delete_email_log",
]
