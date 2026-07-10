from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import os
from emails import EmailSender
from hrms import *
from hrms import tools_impl as ti
from mcp.server.fastmcp import FastMCP

from database import SessionLocal, engine, Base

# Create all tables on startup (safe to call repeatedly — only creates if not exists)
import models  # noqa: F401  — ensures all ORM models are registered with Base
from app.db_migrate import run_portal_migrations

Base.metadata.create_all(bind=engine)
run_portal_migrations()

emailer = EmailSender(
    smtp_server="smtp.gmail.com",
    port=587,
    username=os.getenv("CB_EMAIL"),
    password=os.getenv("CB_EMAIL_PWD"),
    use_tls=True,
)

mcp = FastMCP("atliq-hr-assist")


@contextmanager
def get_managers():
    """
    Context manager that opens a single DB session and returns
    all four manager instances sharing that session.
    Ensures the session is closed after each tool call.
    """
    db = SessionLocal()
    try:
        yield (
            EmployeeManager(db),
            LeaveManager(db),
            MeetingManager(db),
            TicketManager(db),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Employee Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def add_employee(
    emp_name: str,
    email: Optional[str] = None,
    manager_id: Optional[str] = None,
    create_portal_login: bool = False,
    initial_password: Optional[str] = None,
) -> str:
    """
    Add a new employee to the HRMS system.
    :param emp_name: Full name of the employee
    :param email: Work email; omit to auto-set first.last@atom.com from emp_name (also portal username if login is created)
    :param manager_id: Manager's employee ID (leave empty for top-level managers)
    :param create_portal_login: If True, create employee portal credentials (random password if initial_password omitted)
    :param initial_password: Optional portal password (min 8 characters)
    :return: Confirmation message including emp_id and temporary portal password when applicable
    """
    with get_managers() as (em, lm, mm, tm):
        db = em.db
        return ti.add_employee_impl(
            db,
            emp_name,
            email,
            manager_id,
            create_portal_login=create_portal_login,
            initial_password=initial_password,
        )


@mcp.tool()
def find_employee_by_name(name: str) -> Dict[str, str]:
    """
    Search for an employee using their name (supports partial/fuzzy matching).
    Use this tool whenever you only know the employee's name and need to look up
    their emp_id, email, or manager. Do NOT use get_employee_by_id for this.
    :param name: Full or partial name of the employee (e.g. "John", "John Doe")
    :return: Employee details dict including emp_id, name, manager_id, email
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.find_employee_by_name_impl(em.db, name)


@mcp.tool()
def list_managers() -> List[Dict[str, Any]]:
    """
    List all people-manager roster entries (mgr_id M…, name, email, linked_emp_id, status).
    Use for questions like \"list all managers\" or the manager directory — not find_employee_by_name.
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.list_managers_impl(em.db)


@mcp.tool()
def get_employee_by_id(emp_id: str) -> Dict[str, str]:
    """
    Fetch full details of an employee using their exact employee ID (e.g. 'E001').
    Use this tool when you already have the emp_id.
    For name-based lookups, use find_employee_by_name instead.
    :param emp_id: The employee's unique ID (e.g. 'E001')
    :return: Employee details dict including emp_id, name, manager_id, email
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.get_employee_by_id_impl(em.db, emp_id)


# ---------------------------------------------------------------------------
# Email Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def send_email(to_emails: List[str], subject: str, body: str, html: bool = False) -> str:
    """
    Send an email to one or more recipients.
    :param to_emails: List of email addresses
    :param subject: Email subject
    :param body: Email body content
    :param html: Set True to send as HTML email
    :return: Success message
    """
    return ti.send_email_impl(emailer, to_emails, subject, body, html=html)


# ---------------------------------------------------------------------------
# Ticket Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_ticket(emp_id: str, item: str, reason: str) -> str:
    """
    Create an IT support ticket for an employee.
    :param emp_id: Employee ID
    :param item: Item requested (e.g. Laptop, ID Card)
    :param reason: Reason for the request
    :return: Confirmation message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.create_ticket_impl(em.db, emp_id, item, reason, emailer=emailer)


@mcp.tool()
def update_ticket_status(ticket_id: str, status: str) -> str:
    """
    Update the status of a ticket.
    :param ticket_id: Ticket ID (e.g. T0001)
    :param status: New status — one of: Open, In Progress, Closed, Rejected
    :return: Confirmation message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.update_ticket_status_impl(em.db, ticket_id, status, emailer=emailer)


@mcp.tool()
def list_tickets(employee_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict]:
    """
    List tickets, optionally filtered by employee and/or status.
    :param employee_id: (Optional) Employee ID to filter by
    :param status: (Optional) Ticket status to filter by
    :return: List of matching tickets
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.list_tickets_impl(em.db, employee_id=employee_id, status=status)


# ---------------------------------------------------------------------------
# Meeting Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def schedule_meeting(employee_id: str, meeting_datetime: str, topic: str) -> str:
    """
    Schedule a meeting for an employee.
    :param employee_id: Employee ID
    :param meeting_datetime: Date and time in ISO format (YYYY-MM-DDTHH:MM:SS)
    :param topic: Topic of the meeting
    :return: Confirmation message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.schedule_meeting_impl(em.db, employee_id, meeting_datetime, topic)


@mcp.tool()
def get_meetings(employee_id: str) -> List[Dict[str, str]]:
    """
    Get all meetings scheduled for an employee.
    :param employee_id: Employee ID
    :return: List of meetings with date and topic
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.get_meetings_impl(em.db, employee_id)


@mcp.tool()
def cancel_meeting(employee_id: str, meeting_datetime: str, topic: Optional[str] = None) -> str:
    """
    Cancel a scheduled meeting for an employee.
    :param employee_id: Employee ID
    :param meeting_datetime: Date and time in ISO format (YYYY-MM-DDTHH:MM:SS)
    :param topic: (Optional) Topic to match if employee has multiple meetings at the same time
    :return: Confirmation message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.cancel_meeting_impl(em.db, employee_id, meeting_datetime, topic)


# ---------------------------------------------------------------------------
# Leave Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_employee_leave_balance(emp_id: str) -> str:
    """
    Get the current leave balance of an employee.
    :param emp_id: Employee ID
    :return: Leave balance message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.get_employee_leave_balance_impl(em.db, emp_id)


@mcp.tool()
def apply_leave(emp_id: str, leave_dates: list) -> str:
    """
    Apply for leave for an employee.
    :param emp_id: Employee ID
    :param leave_dates: List of leave dates (e.g. ["2025-07-01", "2025-07-02"])
    :return: Leave application status message
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.apply_leave_impl(em.db, emp_id, leave_dates)


@mcp.tool()
def get_leave_history(emp_id: str) -> str:
    """
    Get the leave history of an employee.
    :param emp_id: Employee ID
    :return: Formatted leave history
    """
    with get_managers() as (em, lm, mm, tm):
        return ti.get_leave_history_impl(em.db, emp_id)


# ---------------------------------------------------------------------------
# MCP Prompt Template
# ---------------------------------------------------------------------------


@mcp.prompt("onboard_new_employee")
def onboard_new_employee(employee_name: str, manager_name: str):
    return f"""Onboard a new employee with the following details:
    - Name: {employee_name}
    - Manager Name: {manager_name}
    Steps to follow:
    1. Use the find_employee_by_name tool with the manager's name to get their emp_id. (Important: always use find_employee_by_name for name-based lookups, never get_employee_by_id)
    2. Add the employee to the HRMS system using the manager's emp_id from step 1.
    3. Send a welcome email to the employee with their login credentials. (Format: employee_name@atliq.com)
    4. Notify the manager about the new employee's onboarding.
    5. Raise tickets for a new laptop, id card, and other necessary equipment.
    6. Schedule an introductory meeting between the employee and the manager.
    """


if __name__ == "__main__":
    mcp.run(transport="stdio")
