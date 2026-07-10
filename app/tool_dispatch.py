"""
Map OpenRouter/OpenAI tool names to hrms.tools_impl callables with role checks.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.chat_context import ChatContext
from emails import EmailSender
from hrms import data_admin_service as das
from hrms import tools_impl as ti
from models import ToolCallLog

HR_ONLY = {
    "add_employee",
    "find_employee_by_name",
    "send_email",
    "create_ticket",
    "update_ticket_status",
    "schedule_meeting",
    "cancel_meeting",
    "approve_leave_request",
    "reject_leave_request",
    "apply_leave",
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
    "update_manager",
    "delete_manager",
}

EMPLOYEE_TOOLS = {
    "get_employee_by_id",
    "list_tickets",
    "get_meetings",
    "get_employee_leave_balance",
    "submit_leave_request",
    "get_leave_history",
    "list_leave_requests",
}

HR_TOOLS = HR_ONLY | EMPLOYEE_TOOLS | {
    "list_managers",
    "list_tickets",
    "get_meetings",
    "get_employee_by_id",
    "get_employee_leave_balance",
    "get_leave_history",
    "list_leave_requests",
}


def _log_tool(
    db: Session,
    ctx: ChatContext,
    name: str,
    arguments: Dict[str, Any],
    result: str,
) -> None:
    try:
        preview = (result[:4000] + "…") if len(result) > 4000 else result
        row = ToolCallLog(
            portal_user_id=ctx.portal_user_id,
            role=ctx.role,
            employee_id=ctx.employee_id,
            tool_name=name,
            arguments_json=json.dumps(arguments, default=str),
            result_preview=preview,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()


def _deny(msg: str) -> str:
    return json.dumps({"error": msg})


def dispatch_tool(
    name: str,
    arguments: Dict[str, Any],
    db: Session,
    emailer: EmailSender,
    ctx: ChatContext,
) -> str:
    allowed = HR_TOOLS if ctx.role == "hr" else EMPLOYEE_TOOLS
    if name not in allowed:
        return _deny(f"Tool '{name}' is not available for your role.")

    emp_scope = ctx.employee_id

    def ensure_self_emp(arg_emp: Optional[str], field: str = "emp_id") -> Optional[str]:
        if ctx.role != "employee":
            return arg_emp
        if not emp_scope:
            raise ValueError("Employee session is missing employee_id.")
        if arg_emp and arg_emp != emp_scope:
            raise ValueError("You can only access your own employee record.")
        return emp_scope

    try:
        out: str
        if name == "add_employee":
            out = ti.add_employee_impl(
                db,
                arguments["emp_name"],
                arguments.get("email"),
                arguments.get("manager_id") or None,
                create_portal_login=bool(arguments.get("create_portal_login", False)),
                initial_password=arguments.get("initial_password"),
            )
        elif name == "find_employee_by_name":
            try:
                out = ti.tool_result_to_json(ti.find_employee_by_name_impl(db, arguments["name"]))
            except ValueError as e:
                out = str(e)
        elif name == "list_managers":
            out = ti.tool_result_to_json(ti.list_managers_impl(db))
        elif name == "update_manager":
            mid = arguments["mgr_id"]
            updates = {}
            for k in ("name", "email", "linked_emp_id", "onboarding_status"):
                if k in arguments:
                    updates[k] = arguments[k]
            out = ti.tool_result_to_json(das.update_manager(db, mid, updates))
        elif name == "delete_manager":
            out = ti.tool_result_to_json(das.delete_manager(db, arguments["mgr_id"]))
        elif name == "get_employee_by_id":
            eid = ensure_self_emp(arguments.get("emp_id"), "emp_id")
            if not eid:
                return _deny("emp_id is required.")
            out = ti.tool_result_to_json(ti.get_employee_by_id_impl(db, eid))
        elif name == "send_email":
            out = ti.send_email_impl(
                emailer,
                list(arguments["to_emails"]),
                arguments["subject"],
                arguments["body"],
                html=bool(arguments.get("html", False)),
            )
        elif name == "create_ticket":
            out = ti.create_ticket_impl(
                db,
                arguments["emp_id"],
                arguments["item"],
                arguments["reason"],
                title=arguments.get("title"),
                department=arguments.get("department"),
                created_by_emp_id=arguments.get("created_by_emp_id") or ctx.effective_approver(),
                emailer=emailer,
            )
        elif name == "update_ticket_status":
            out = ti.update_ticket_status_impl(
                db,
                arguments["ticket_id"],
                arguments["status"],
                emailer=emailer,
            )
        elif name == "list_tickets":
            eid = arguments.get("employee_id")
            if ctx.role == "employee":
                eid = emp_scope
            out = ti.tool_result_to_json(
                ti.list_tickets_impl(db, employee_id=eid, status=arguments.get("status"))
            )
        elif name == "schedule_meeting":
            out = ti.schedule_meeting_impl(
                db,
                arguments["employee_id"],
                arguments["meeting_datetime"],
                arguments["topic"],
                hr_emp_id=arguments.get("hr_emp_id") or ctx.effective_approver(),
                agenda=arguments.get("agenda"),
                location_or_link=arguments.get("location_or_link"),
            )
        elif name == "get_meetings":
            raw = arguments.get("employee_id") or arguments.get("emp_id")
            eid = ensure_self_emp(raw)
            if not eid:
                return _deny("employee_id is required.")
            out = ti.tool_result_to_json(ti.get_meetings_impl(db, eid))
        elif name == "cancel_meeting":
            out = ti.cancel_meeting_impl(
                db,
                arguments["employee_id"],
                arguments["meeting_datetime"],
                arguments.get("topic"),
            )
        elif name == "get_employee_leave_balance":
            eid = ensure_self_emp(arguments.get("emp_id"))
            if not eid:
                return _deny("emp_id is required.")
            out = ti.get_employee_leave_balance_impl(db, eid)
        elif name == "apply_leave":
            out = ti.apply_leave_impl(db, arguments["emp_id"], arguments["leave_dates"])
        elif name == "submit_leave_request":
            if ctx.role == "employee":
                eid = ensure_self_emp(arguments.get("emp_id"))
            else:
                eid = arguments.get("emp_id") or arguments.get("employee_id")
            if not eid:
                return _deny("emp_id is required.")
            out = ti.submit_leave_request_impl(
                db,
                eid,
                arguments["start_date"],
                arguments["end_date"],
                arguments["reason"],
                arguments.get("message"),
            )
        elif name == "list_leave_requests":
            eid = arguments.get("employee_id")
            st = arguments.get("status")
            if ctx.role == "employee":
                eid = emp_scope
            out = ti.tool_result_to_json(ti.list_leave_requests_impl(db, emp_id=eid, status=st))
        elif name == "approve_leave_request":
            approver = arguments.get("approver_emp_id") or ctx.effective_approver()
            out = ti.approve_leave_request_impl(db, int(arguments["request_id"]), approver)
        elif name == "reject_leave_request":
            approver = arguments.get("approver_emp_id") or ctx.effective_approver()
            out = ti.reject_leave_request_impl(db, int(arguments["request_id"]), approver)
        elif name == "get_leave_history":
            eid = ensure_self_emp(arguments.get("emp_id"))
            if not eid:
                return _deny("emp_id is required.")
            out = ti.get_leave_history_impl(db, eid)
        elif name == "list_employees":
            out = ti.tool_result_to_json(das.list_employees(db))
        elif name == "update_employee":
            eid = arguments["emp_id"]
            updates = {}
            for k in ("name", "email", "manager_id"):
                if k in arguments:
                    updates[k] = arguments[k]
            out = ti.tool_result_to_json(das.update_employee(db, eid, updates))
        elif name == "delete_employee":
            out = ti.tool_result_to_json(das.delete_employee(db, arguments["emp_id"]))
        elif name == "list_leave_balances":
            out = ti.tool_result_to_json(das.list_leave_balances(db))
        elif name == "set_leave_balance":
            out = ti.tool_result_to_json(
                das.set_leave_balance(db, arguments["emp_id"], int(arguments["balance"]))
            )
        elif name == "list_leave_history_records":
            lim = int(arguments["limit"]) if arguments.get("limit") is not None else 500
            out = ti.tool_result_to_json(
                das.list_leave_history(db, emp_id=arguments.get("emp_id"), limit=lim)
            )
        elif name == "add_leave_history_record":
            out = ti.tool_result_to_json(
                das.create_leave_history(
                    db,
                    arguments["emp_id"],
                    arguments["leave_date"],
                    int(arguments["request_id"]),
                )
            )
        elif name == "delete_leave_history_record":
            out = ti.tool_result_to_json(das.delete_leave_history(db, int(arguments["row_id"])))
        elif name == "list_all_meetings":
            out = ti.tool_result_to_json(
                das.list_meetings(db, emp_id=arguments.get("employee_id") or arguments.get("emp_id"))
            )
        elif name == "update_meeting":
            mid = int(arguments["meeting_id"])
            kw: Dict[str, Any] = {}
            if arguments.get("emp_id") is not None:
                kw["emp_id"] = arguments["emp_id"]
            if arguments.get("meeting_dt") is not None:
                kw["meeting_dt"] = arguments["meeting_dt"]
            if arguments.get("topic") is not None:
                kw["topic"] = arguments["topic"]
            out = ti.tool_result_to_json(das.update_meeting(db, mid, **kw))
        elif name == "delete_meeting_by_id":
            out = ti.tool_result_to_json(das.delete_meeting(db, int(arguments["meeting_id"])))
        elif name == "list_all_tickets_admin":
            out = ti.tool_result_to_json(das.list_all_tickets(db))
        elif name == "update_ticket_fields":
            out = ti.tool_result_to_json(
                das.patch_ticket_full(
                    db,
                    arguments["ticket_id"],
                    item=arguments.get("item"),
                    reason=arguments.get("reason"),
                    status=arguments.get("status"),
                    emailer=emailer,
                )
            )
        elif name == "delete_ticket":
            out = ti.tool_result_to_json(das.delete_ticket(db, arguments["ticket_id"]))
        elif name == "list_email_logs":
            lim = int(arguments["limit"]) if arguments.get("limit") is not None else 200
            off = int(arguments["offset"]) if arguments.get("offset") is not None else 0
            out = ti.tool_result_to_json(
                das.list_email_logs(
                    db,
                    emp_id=arguments.get("emp_id"),
                    limit=lim,
                    offset=off,
                )
            )
        elif name == "delete_email_log":
            out = ti.tool_result_to_json(das.delete_email_log(db, int(arguments["log_id"])))
        else:
            out = json.dumps({"error": f"Unknown tool: {name}"})

        _log_tool(db, ctx, name, arguments, out)
        return out
    except KeyError as e:
        err = f"Missing or invalid tool argument: {e!s}"
        _log_tool(db, ctx, name, arguments, err)
        return err
    except Exception as e:
        err = f"Error executing {name}: {e!s}"
        _log_tool(db, ctx, name, arguments, err)
        return err


def dispatch_hr_tool(
    name: str,
    arguments: Dict[str, Any],
    db: Session,
    emailer: EmailSender,
) -> str:
    """Backward-compatible entry point (MCP / legacy callers): full HR tool set."""
    return dispatch_tool(name, arguments, db, emailer, ChatContext(role="hr"))
