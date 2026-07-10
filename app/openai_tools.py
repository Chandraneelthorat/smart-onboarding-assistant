"""
OpenAI / OpenRouter-compatible tool definitions for HR vs Employee chat.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _fn(
    name: str,
    description: str,
    properties: Dict[str, Any],
    required: List[str],
) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


HR_TOOL_SPECS: List[Dict[str, Any]] = [
    _fn(
        "add_employee",
        "Register a new employee; returns emp_id. Set create_portal_login true to create employee "
        "portal sign-in (username = work email, random password unless initial_password is set). "
        "Work email defaults to first.last@atom.com derived from emp_name when email is omitted.",
        {
            "emp_name": {"type": "string"},
            "email": {
                "type": "string",
                "description": "Optional. Omit or leave empty to auto-set first.last@atom.com from emp_name (Atom).",
            },
            "manager_id": {
                "type": "string",
                "description": "Reporting manager HRMS emp_id (E…). If the user gives a people-manager roster id (M…), "
                "call list_managers and use that row's linked_emp_id as manager_id.",
            },
            "create_portal_login": {
                "type": "boolean",
                "description": "If true, create username/password for the employee portal (same email as work email).",
            },
            "initial_password": {
                "type": "string",
                "description": "Optional; min 8 chars. If omitted, a secure random password is generated.",
            },
        },
        ["emp_name"],
    ),
    _fn(
        "find_employee_by_name",
        "Find an employee by name (fuzzy); returns emp_id and details.",
        {"name": {"type": "string"}},
        ["name"],
    ),
    _fn(
        "list_managers",
        "List every people-manager roster entry (mgr_id M…, name, email, linked_emp_id if set, status). "
        "Use this when the user asks for all managers, the manager directory, or manager roster — "
        "not find_employee_by_name (that only searches HRMS employees and returns one match).",
        {},
        [],
    ),
    _fn(
        "update_manager",
        "Update a people-manager roster row by mgr_id (M…). linked_emp_id must be an existing emp_id (E…) or null/empty to unlink.",
        {
            "mgr_id": {"type": "string"},
            "name": {"type": "string"},
            "email": {"type": "string"},
            "linked_emp_id": {"type": "string", "description": "HRMS employee id or empty to clear"},
            "onboarding_status": {"type": "string"},
        },
        ["mgr_id"],
    ),
    _fn(
        "delete_manager",
        "Remove a manager roster row by mgr_id (does not delete the linked HRMS employee).",
        {"mgr_id": {"type": "string"}},
        ["mgr_id"],
    ),
    _fn(
        "get_employee_by_id",
        "Get profile details for an employee by emp_id.",
        {"emp_id": {"type": "string"}},
        ["emp_id"],
    ),
    _fn(
        "send_email",
        "Send email via company SMTP.",
        {
            "to_emails": {"type": "array", "items": {"type": "string"}},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "html": {"type": "boolean"},
        },
        ["to_emails", "subject", "body"],
    ),
    _fn(
        "create_ticket",
        "Create a support/ticket for an employee.",
        {
            "emp_id": {"type": "string"},
            "item": {"type": "string"},
            "reason": {"type": "string"},
            "title": {"type": "string"},
            "department": {"type": "string"},
            "created_by_emp_id": {"type": "string"},
        },
        ["emp_id", "item", "reason"],
    ),
    _fn(
        "update_ticket_status",
        "Update ticket status by ticket_id (e.g. T0001).",
        {
            "ticket_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["Open", "In Progress", "Closed", "Rejected"],
            },
        },
        ["ticket_id", "status"],
    ),
    _fn(
        "list_tickets",
        "List tickets; optional filters.",
        {
            "employee_id": {"type": "string"},
            "status": {"type": "string"},
        },
        [],
    ),
    _fn(
        "schedule_meeting",
        "Schedule a meeting. meeting_datetime ISO-8601.",
        {
            "employee_id": {"type": "string"},
            "meeting_datetime": {"type": "string"},
            "topic": {"type": "string"},
            "hr_emp_id": {"type": "string"},
            "agenda": {"type": "string"},
            "location_or_link": {"type": "string"},
        },
        ["employee_id", "meeting_datetime", "topic"],
    ),
    _fn(
        "get_meetings",
        "List meetings for an employee.",
        {"employee_id": {"type": "string"}},
        ["employee_id"],
    ),
    _fn(
        "cancel_meeting",
        "Cancel a meeting for an employee at a given datetime.",
        {
            "employee_id": {"type": "string"},
            "meeting_datetime": {"type": "string"},
            "topic": {"type": "string"},
        },
        ["employee_id", "meeting_datetime"],
    ),
    _fn(
        "get_employee_leave_balance",
        "Get remaining leave balance for an employee.",
        {"emp_id": {"type": "string"}},
        ["emp_id"],
    ),
    _fn(
        "apply_leave",
        "Immediately deduct leave (legacy/admin). Prefer approve_leave_request workflow for employees.",
        {
            "emp_id": {"type": "string"},
            "leave_dates": {"type": "array", "items": {"type": "string"}},
        },
        ["emp_id", "leave_dates"],
    ),
    _fn(
        "submit_leave_request",
        "Submit a leave request pending HR approval (start/end ISO dates).",
        {
            "emp_id": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "reason": {"type": "string"},
            "message": {"type": "string"},
        },
        ["emp_id", "start_date", "end_date", "reason"],
    ),
    _fn(
        "list_leave_requests",
        "List leave requests (each row includes employee_id, employee_name, dates, status). HR can filter by employee_id and status.",
        {
            "employee_id": {"type": "string"},
            "status": {"type": "string"},
        },
        [],
    ),
    _fn(
        "approve_leave_request",
        "Approve a pending leave request by numeric request_id.",
        {
            "request_id": {"type": "integer"},
            "approver_emp_id": {"type": "string", "description": "Usually inferred from session"},
        },
        ["request_id"],
    ),
    _fn(
        "reject_leave_request",
        "Reject a pending leave request.",
        {
            "request_id": {"type": "integer"},
            "approver_emp_id": {"type": "string"},
        },
        ["request_id"],
    ),
    _fn(
        "get_leave_history",
        "Leave history and workflow requests for an employee.",
        {"emp_id": {"type": "string"}},
        ["emp_id"],
    ),
    _fn(
        "list_employees",
        "List all HRMS employees (emp_id, name, manager_id, email). Same data as the Data console.",
        {},
        [],
    ),
    _fn(
        "update_employee",
        "Update an employee record (partial). manager_id must be an existing emp_id or omit/null to clear.",
        {
            "emp_id": {"type": "string"},
            "name": {"type": "string"},
            "email": {"type": "string"},
            "manager_id": {"type": "string", "description": "Reporting manager emp_id (E…) or empty to clear"},
        },
        ["emp_id"],
    ),
    _fn(
        "delete_employee",
        "Permanently delete an employee and dependent rows (destructive). Requires exact emp_id.",
        {"emp_id": {"type": "string"}},
        ["emp_id"],
    ),
    _fn(
        "list_leave_balances",
        "List leave balance rows for all employees.",
        {},
        [],
    ),
    _fn(
        "set_leave_balance",
        "Set leave balance (days remaining) for one employee.",
        {"emp_id": {"type": "string"}, "balance": {"type": "integer", "minimum": 0}},
        ["emp_id", "balance"],
    ),
    _fn(
        "list_leave_history_records",
        "List approved leave history rows (id, emp_id, leave_date, request_id). Optional filter by emp_id.",
        {
            "emp_id": {"type": "string"},
            "limit": {"type": "integer", "description": "Max rows (default 500)"},
        },
        [],
    ),
    _fn(
        "add_leave_history_record",
        "Insert a leave history row (admin). leave_date YYYY-MM-DD.",
        {
            "emp_id": {"type": "string"},
            "leave_date": {"type": "string"},
            "request_id": {"type": "integer"},
        },
        ["emp_id", "leave_date", "request_id"],
    ),
    _fn(
        "delete_leave_history_record",
        "Delete one leave history row by its numeric id (from list_leave_history_records).",
        {"row_id": {"type": "integer"}},
        ["row_id"],
    ),
    _fn(
        "list_all_meetings",
        "List meetings (numeric id, emp_id, meeting_dt, topic). Omit employee_id to list all.",
        {"employee_id": {"type": "string"}},
        [],
    ),
    _fn(
        "update_meeting",
        "Update a meeting by numeric database id (from list_all_meetings).",
        {
            "meeting_id": {"type": "integer"},
            "emp_id": {"type": "string"},
            "meeting_dt": {"type": "string", "description": "ISO datetime"},
            "topic": {"type": "string"},
        },
        ["meeting_id"],
    ),
    _fn(
        "delete_meeting_by_id",
        "Delete a meeting row by numeric database id.",
        {"meeting_id": {"type": "integer"}},
        ["meeting_id"],
    ),
    _fn(
        "list_all_tickets_admin",
        "List every ticket (same as Data console tickets-all).",
        {},
        [],
    ),
    _fn(
        "update_ticket_fields",
        "Update ticket item, reason, and/or status (Open, In Progress, Closed, Rejected). Sends employee email when closing if SMTP configured.",
        {
            "ticket_id": {"type": "string"},
            "item": {"type": "string"},
            "reason": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["Open", "In Progress", "Closed", "Rejected"],
            },
        },
        ["ticket_id"],
    ),
    _fn(
        "delete_ticket",
        "Permanently delete a ticket by ticket_id (e.g. T0001).",
        {"ticket_id": {"type": "string"}},
        ["ticket_id"],
    ),
    _fn(
        "list_email_logs",
        "List stored email log entries. Optional emp_id filter, limit, offset.",
        {
            "emp_id": {"type": "string"},
            "limit": {"type": "integer"},
            "offset": {"type": "integer"},
        },
        [],
    ),
    _fn(
        "delete_email_log",
        "Delete one email log row by numeric id.",
        {"log_id": {"type": "integer"}},
        ["log_id"],
    ),
]

EMPLOYEE_TOOL_SPECS: List[Dict[str, Any]] = [
    _fn(
        "get_employee_by_id",
        "Get your profile (emp_id will be scoped to the logged-in user).",
        {"emp_id": {"type": "string"}},
        [],
    ),
    _fn(
        "list_tickets",
        "List tickets assigned to you.",
        {},
        [],
    ),
    _fn(
        "get_meetings",
        "List meetings scheduled for you.",
        {"employee_id": {"type": "string"}},
        [],
    ),
    _fn(
        "get_employee_leave_balance",
        "Your remaining leave balance.",
        {"emp_id": {"type": "string"}},
        [],
    ),
    _fn(
        "submit_leave_request",
        "Apply for leave (pending HR approval). Dates as YYYY-MM-DD.",
        {
            "emp_id": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "reason": {"type": "string"},
            "message": {"type": "string"},
        },
        ["start_date", "end_date", "reason"],
    ),
    _fn(
        "list_leave_requests",
        "Your leave requests and statuses (includes employee_name when present).",
        {},
        [],
    ),
    _fn(
        "get_leave_history",
        "Approved leave history and request log.",
        {"emp_id": {"type": "string"}},
        [],
    ),
]


HR_SYSTEM_PROMPT = """You are HR-ASSIST for HR staff. You manage employees, email, tickets, meetings, \
and leave in the company HRMS. Use tools to perform actions; do not invent employee IDs — use \
find_employee_by_name or get_employee_by_id. The people-manager roster is separate: each row has mgr_id \
(M-prefixed) and may link to an HRMS employee via linked_emp_id (E-prefixed). When the user asks to list \
all managers, the manager roster, or people managers, call list_managers (not find_employee_by_name). \
For onboarding-style flows, collect missing fields before calling tools, except: do not ask for the new \
hire's work email when you already have their full name — the system uses Atom's convention \
first.last@atom.com (single names: localpart@atom.com) automatically when email is omitted. \
add_employee manager_id is the reporting manager's HRMS emp_id (E…); if the user only knows an M… roster id, \
call list_managers and use linked_emp_id for that row. When adding an employee who should access the \
employee portal, call add_employee with create_portal_login true (a random password is generated unless the \
user gives initial_password). Return the temporary password to HR only — it is shown once. Be concise and \
professional. For leave approval, use list_leave_requests to find request_id, then approve_leave_request \
or reject_leave_request. You have the same data-admin capabilities as the HR Data console: list/update/delete \
employees, leave balances, leave history rows, meetings (by numeric id), full ticket edits, and email logs — \
use the matching tools (list_employees, update_employee, delete_employee, list_leave_balances, set_leave_balance, \
list_leave_history_records, add_leave_history_record, delete_leave_history_record, list_all_meetings, \
update_meeting, delete_meeting_by_id, list_all_tickets_admin, update_ticket_fields, delete_ticket, \
list_email_logs, delete_email_log). Manager roster (M ids) can be edited with update_manager or delete_manager. \
Confirm destructive actions with the user when appropriate. \
Format every reply as plain text: do not use Markdown (no **bold**), and do not \
start lines with hyphen or asterisk bullets; use numbered lines (1. 2.) or lines like Label: value instead."""

EMPLOYEE_SYSTEM_PROMPT = """You are HR-ASSIST for an employee. You may only access this user's own HR \
data; tools are automatically scoped. Help them view manager info, tickets, meetings, leave balance, \
submit leave requests with clear dates and reason, and view history. Ask for missing dates or reason \
before calling submit_leave_request. Be concise and friendly. Use plain text only: no Markdown bold (**), \
and no hyphen or asterisk bullets; use numbers or Label: value lines."""


def tools_for_role(role: str) -> List[Dict[str, Any]]:
    return HR_TOOL_SPECS if role == "hr" else EMPLOYEE_TOOL_SPECS


def system_prompt_for_role(role: str) -> str:
    return HR_SYSTEM_PROMPT if role == "hr" else EMPLOYEE_SYSTEM_PROMPT


# Backward compatibility
OPENROUTER_TOOLS = HR_TOOL_SPECS
SYSTEM_PROMPT = HR_SYSTEM_PROMPT
