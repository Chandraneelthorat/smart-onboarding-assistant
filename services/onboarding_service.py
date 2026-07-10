"""
Deterministic onboarding flow for the REST wizard (same steps as MCP prompt).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from emails import EmailSender
from hrms import tools_impl as ti
from hrms.manager_manager import add_manager_get_id
from models import Manager


def _send_onboarding_email(
    emailer: EmailSender,
    *,
    to_emails: List[str],
    subject: str,
    body: str,
) -> str:
    """SMTP failures must not roll back a successful hire; return a clear status string."""
    recipients = [x for x in to_emails if x and str(x).strip()]
    if not recipients:
        return "Email skipped (no recipient address)."
    try:
        return ti.send_email_impl(emailer, recipients, subject, body, html=False)
    except Exception as e:
        return (
            "Email was not sent (new hire was still created). "
            "Set CB_EMAIL and CB_EMAIL_PWD for Gmail SMTP, or fix your mail setup. "
            f"Error: {e!s}"
        )


def _default_meeting_iso() -> str:
    base = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    nxt = base + timedelta(days=1)
    return nxt.isoformat()


_WELCOME_EMAIL_SKIPPED = (
    "Welcome email to the new hire was not sent (work email is often a placeholder). "
    "Share the portal login from this screen using your own channel."
)


def run_onboarding(
    db: Session,
    emailer: EmailSender,
    *,
    employee_name: str,
    employee_email: str,
    manager_mgr_id: Optional[str] = None,
    manager_name: Optional[str] = None,
    meeting_datetime: Optional[str] = None,
    meeting_topic: str = "Introduction and onboarding kickoff",
    hr_emp_id: Optional[str] = None,
    initial_portal_password: Optional[str] = None,
) -> Dict[str, Any]:
    mid = (manager_mgr_id or "").strip()
    mn = (manager_name or "").strip()
    reporting_manager_mgr_id = ""

    if mid:
        row = db.query(Manager).filter(Manager.mgr_id == mid).first()
        if not row:
            raise ValueError(f"Manager ID '{mid}' not found.")
        link = (row.linked_emp_id or "").strip()
        if not link:
            raise ValueError(
                f"Manager '{mid}' has no linked employee record; set linked_emp_id before assigning reports."
            )
        try:
            emp_detail = ti.get_employee_by_id_impl(db, link)
        except ValueError as exc:
            raise ValueError(
                f"Manager roster '{mid}' points to missing employee {link!r}. "
                "Fix linked_emp_id in the managers table."
            ) from exc
        manager_emp_id = link
        manager_display_name = row.name
        manager_email = emp_detail.get("email") or ""
        reporting_manager_mgr_id = mid
    elif mn:
        manager = ti.find_employee_by_name_impl(db, mn)
        manager_emp_id = manager["emp_id"]
        manager_display_name = mn
        manager_email = manager.get("email") or ""
        mgr_row = db.query(Manager).filter(Manager.linked_emp_id == manager_emp_id).first()
        reporting_manager_mgr_id = mgr_row.mgr_id if mgr_row else ""
    else:
        raise ValueError("Provide manager_mgr_id or manager_name for employee onboarding.")

    new_emp_id, portal_user, portal_pw, portal_err = ti.add_employee_get_id(
        db,
        employee_name,
        employee_email,
        manager_id=manager_emp_id,
        create_portal_login=True,
        initial_password=initial_portal_password,
    )

    welcome_result = _WELCOME_EMAIL_SKIPPED

    manager_notice = ""
    if manager_email:
        mgr_body = (
            f"Hello {manager_display_name},\n\n"
            f"{employee_name} ({new_emp_id}) has been added to the HRMS as your direct report. "
            f"Their email is {employee_email}.\n"
        )
        manager_notice = _send_onboarding_email(
            emailer,
            to_emails=[manager_email],
            subject=f"New team member: {employee_name}",
            body=mgr_body,
        )

    tickets_out: List[str] = []
    for item, reason, title in (
        ("Laptop", "New hire onboarding — hardware", "Laptop assignment"),
        ("ID Card", "New hire onboarding — facilities", "ID card assignment"),
    ):
        tickets_out.append(
            ti.create_ticket_impl(
                db,
                new_emp_id,
                item,
                reason,
                title=title,
                department="IT",
                created_by_emp_id=hr_emp_id,
                emailer=None,
            )
        )

    mtg_iso = meeting_datetime or _default_meeting_iso()
    meeting_result = ti.schedule_meeting_impl(
        db,
        new_emp_id,
        mtg_iso,
        meeting_topic,
        hr_emp_id=hr_emp_id,
    )

    return {
        "hire_kind": "employee",
        "new_employee_id": new_emp_id,
        "new_manager_id": "",
        "manager_id": manager_emp_id,
        "reporting_manager_mgr_id": reporting_manager_mgr_id,
        "welcome_email": welcome_result,
        "manager_email_result": manager_notice,
        "tickets": tickets_out,
        "meeting": meeting_result,
        "meeting_datetime_used": mtg_iso,
        "portal_username": portal_user,
        "portal_password": portal_pw,
        "portal_login_error": portal_err,
    }


def run_manager_hire(
    db: Session,
    *,
    employee_name: str,
    employee_email: str,
    meeting_datetime: Optional[str] = None,
    meeting_topic: str = "Introduction and onboarding kickoff",
    hr_emp_id: Optional[str] = None,
    initial_portal_password: Optional[str] = None,
) -> Dict[str, Any]:
    """People-manager hire: `employees` row (IT/leave/meetings) + `managers` roster row linked by `linked_emp_id`."""
    new_emp_id, portal_user, portal_pw, portal_err = ti.add_employee_get_id(
        db,
        employee_name,
        employee_email,
        manager_id=None,
        create_portal_login=True,
        initial_password=initial_portal_password,
    )
    mgr_id = add_manager_get_id(
        db,
        employee_name,
        employee_email,
        linked_emp_id=new_emp_id,
    )

    welcome_result = _WELCOME_EMAIL_SKIPPED

    tickets_out: List[str] = []
    for item, reason, title in (
        ("Laptop", "New hire onboarding — hardware", "Laptop assignment"),
        ("ID Card", "New hire onboarding — facilities", "ID card assignment"),
    ):
        tickets_out.append(
            ti.create_ticket_impl(
                db,
                new_emp_id,
                item,
                reason,
                title=title,
                department="IT",
                created_by_emp_id=hr_emp_id,
                emailer=None,
            )
        )

    mtg_iso = meeting_datetime or _default_meeting_iso()
    meeting_result = ti.schedule_meeting_impl(
        db,
        new_emp_id,
        mtg_iso,
        meeting_topic,
        hr_emp_id=hr_emp_id,
        display_participant_id=mgr_id,
    )

    return {
        "hire_kind": "manager",
        "new_employee_id": new_emp_id,
        "new_manager_id": mgr_id,
        "manager_id": "",
        "welcome_email": welcome_result,
        "manager_email_result": "",
        "tickets": tickets_out,
        "meeting": meeting_result,
        "meeting_datetime_used": mtg_iso,
        "portal_username": portal_user,
        "portal_password": portal_pw,
        "portal_login_error": portal_err,
    }
