"""Best-effort email to employees for ticket lifecycle (SMTP optional; failures are swallowed)."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

from models import Employee, Ticket

if TYPE_CHECKING:
    from emails import EmailSender


def _recipient_email(db: Session, emp_id: str) -> Optional[str]:
    row = db.query(Employee).filter(Employee.emp_id == emp_id).first()
    if not row or not row.email:
        return None
    s = str(row.email).strip()
    return s or None


def _safe_send(
    emailer: "EmailSender",
    to_addresses: list[str],
    subject: str,
    body: str,
) -> None:
    if not to_addresses:
        return
    try:
        emailer.send_email(
            subject,
            body,
            to_addresses,
            from_email=emailer.username,
            html=False,
        )
    except Exception:
        pass


def notify_employee_new_ticket(
    db: Session, emailer: Optional["EmailSender"], ticket: Ticket
) -> None:
    if not emailer:
        return
    to = _recipient_email(db, ticket.emp_id)
    if not to:
        return
    title = ticket.title or ticket.item
    body = (
        "You have a new support ticket in HR-ASSIST.\n\n"
        f"Ticket ID: {ticket.ticket_id}\n"
        f"Subject: {title}\n"
        f"Details: {ticket.reason}\n\n"
        "Sign in to the employee portal to track status.\n"
    )
    _safe_send(
        emailer,
        [to],
        f"[HR-ASSIST] New ticket {ticket.ticket_id}: {title}",
        body,
    )


def notify_employee_ticket_resolved(
    db: Session, emailer: Optional["EmailSender"], ticket: Ticket
) -> None:
    if not emailer:
        return
    to = _recipient_email(db, ticket.emp_id)
    if not to:
        return
    title = ticket.title or ticket.item
    body = (
        "Your support ticket has been marked resolved (closed) by HR.\n\n"
        f"Ticket ID: {ticket.ticket_id}\n"
        f"Subject: {title}\n\n"
        "Sign in to the employee portal to review. You may also see an in-app notice until you dismiss it.\n"
    )
    _safe_send(
        emailer,
        [to],
        f"[HR-ASSIST] Resolved: {ticket.ticket_id} — {title}",
        body,
    )
