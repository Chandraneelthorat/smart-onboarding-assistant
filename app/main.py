"""
FastAPI HTTP API for HR-ASSIST (wizard + OpenRouter chat + HR tools).
Run: uv run python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.auth import verify_api_key
from app.chat_deps import get_chat_context
from app.chat_context import ChatContext
from app.deps import get_db, get_emailer
from app.schemas import (
    CancelMeetingBody,
    ChatHistoryResponse,
    ChatMessageIn,
    ChatRequest,
    ChatResponse,
    CreateTicketBody,
    EmployeeCreateBody,
    LeaveApplyBody,
    LeaveRequestSubmitBody,
    MessageResponse,
    OnboardingRunBody,
    ScheduleMeetingBody,
    SendEmailBody,
    UpdateTicketBody,
)
from app.openrouter_chat import run_chat_with_tools
from emails import EmailSender
from hrms import EmployeeManager
from hrms import tools_impl as ti
from app.routers import data_crud, portal_auth, portal_data
from services import chat_memory as chat_mem
from services.onboarding_service import run_manager_hire, run_onboarding


def _cors_origins() -> List[str]:
    raw = os.getenv(
        "HR_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173,"
        "http://localhost:8000,http://127.0.0.1:8000",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="HR-ASSIST API", version="0.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api", dependencies=[Depends(verify_api_key)])
public = APIRouter(prefix="/api")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Employees
# ---------------------------------------------------------------------------


@api.post("/employees", response_model=MessageResponse)
def create_employee(
    body: EmployeeCreateBody,
    db: Session = Depends(get_db),
) -> MessageResponse:
    msg = ti.add_employee_impl(
        db,
        body.emp_name,
        body.email,
        body.manager_id,
        create_portal_login=body.create_portal_login,
        initial_password=body.initial_password,
    )
    return MessageResponse(message=msg)


@api.get("/employees/search")
def search_employees(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    em = EmployeeManager(db)
    matches = em.search_employee_by_name(q)
    if not matches:
        return {"matches": []}
    out = []
    for mid in matches[:20]:
        out.append(em.get_employee_details(mid))
    return {"matches": out}


@api.get("/employees/find")
def find_employee(
    name: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        emp = ti.find_employee_by_name_impl(db, name)
        return {"employee": emp}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@api.get("/employees/{emp_id}")
def get_employee(emp_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        return ti.get_employee_by_id_impl(db, emp_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Leave
# ---------------------------------------------------------------------------


@api.get("/employees/{emp_id}/leave/balance", response_model=MessageResponse)
def leave_balance(emp_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    return MessageResponse(message=ti.get_employee_leave_balance_impl(db, emp_id))


@api.get("/employees/{emp_id}/leave/history", response_model=MessageResponse)
def leave_history(emp_id: str, db: Session = Depends(get_db)) -> MessageResponse:
    return MessageResponse(message=ti.get_leave_history_impl(db, emp_id))


@api.get("/leave/requests")
def leave_requests_list(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = ti.list_leave_requests_impl(db, emp_id=employee_id, status=status)
    return {"leave_requests": rows}


@api.post("/leave/apply", response_model=MessageResponse)
def leave_apply(body: LeaveApplyBody, db: Session = Depends(get_db)) -> MessageResponse:
    return MessageResponse(message=ti.apply_leave_impl(db, body.emp_id, body.leave_dates))


@api.post("/leave/request", response_model=MessageResponse)
def leave_request_submit(
    body: LeaveRequestSubmitBody,
    db: Session = Depends(get_db),
) -> MessageResponse:
    try:
        msg = ti.submit_leave_request_impl(
            db,
            body.emp_id,
            body.start_date,
            body.end_date,
            body.reason,
            body.message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return MessageResponse(message=msg)


# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------


@api.post("/meetings", response_model=MessageResponse)
def schedule_meeting(
    body: ScheduleMeetingBody,
    db: Session = Depends(get_db),
) -> MessageResponse:
    msg = ti.schedule_meeting_impl(
        db,
        body.employee_id,
        body.meeting_datetime,
        body.topic,
        hr_emp_id=body.hr_emp_id,
        agenda=body.agenda,
        location_or_link=body.location_or_link,
    )
    return MessageResponse(message=msg)


@api.get("/meetings")
def list_meetings(
    employee_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = ti.get_meetings_impl(db, employee_id)
    return {"meetings": rows}


@api.post("/meetings/cancel", response_model=MessageResponse)
def cancel_meeting(
    body: CancelMeetingBody,
    db: Session = Depends(get_db),
) -> MessageResponse:
    msg = ti.cancel_meeting_impl(
        db,
        body.employee_id,
        body.meeting_datetime,
        body.topic,
    )
    return MessageResponse(message=msg)


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


@api.post("/tickets", response_model=MessageResponse)
def create_ticket(
    body: CreateTicketBody,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
) -> MessageResponse:
    return MessageResponse(
        message=ti.create_ticket_impl(
            db,
            body.emp_id,
            body.item,
            body.reason,
            title=body.title,
            department=body.department,
            created_by_emp_id=body.created_by_emp_id,
            emailer=emailer,
        )
    )


@api.get("/tickets")
def list_tickets(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    rows = ti.list_tickets_impl(db, employee_id=employee_id, status=status)
    return {"tickets": rows}


@api.patch("/tickets/{ticket_id}", response_model=MessageResponse)
def update_ticket(
    ticket_id: str,
    body: UpdateTicketBody,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
) -> MessageResponse:
    try:
        msg = ti.update_ticket_status_impl(
            db, ticket_id, body.status, emailer=emailer
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return MessageResponse(message=msg)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


@api.post("/emails/send", response_model=MessageResponse)
def send_email(
    body: SendEmailBody,
    emailer: EmailSender = Depends(get_emailer),
) -> MessageResponse:
    try:
        msg = ti.send_email_impl(
            emailer,
            body.to_emails,
            body.subject,
            body.body,
            html=body.html,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Email failed: {e!s}")
    return MessageResponse(message=msg)


# ---------------------------------------------------------------------------
# Onboarding wizard
# ---------------------------------------------------------------------------


@api.post("/onboarding/run", response_model=Dict[str, Any])
def onboarding_run(
    body: OnboardingRunBody,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
) -> Dict[str, Any]:
    try:
        if body.is_manager_hire:
            return run_manager_hire(
                db,
                employee_name=body.employee_name,
                employee_email=body.employee_email,
                meeting_datetime=body.meeting_datetime,
                meeting_topic=body.meeting_topic,
                hr_emp_id=body.hr_emp_id,
                initial_portal_password=body.initial_portal_password,
            )
        return run_onboarding(
            db,
            emailer,
            employee_name=body.employee_name,
            employee_email=body.employee_email,
            manager_mgr_id=(body.manager_mgr_id or "").strip() or None,
            manager_name=(body.manager_name or "").strip() or None,
            meeting_datetime=body.meeting_datetime,
            meeting_topic=body.meeting_topic,
            hr_emp_id=body.hr_emp_id,
            initial_portal_password=body.initial_portal_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Onboarding failed: {e!s}",
        ) from e


# ---------------------------------------------------------------------------
# Chat (API key or JWT; not only verify_api_key)
# ---------------------------------------------------------------------------


@public.get("/chat/conversation/{conversation_id}", response_model=ChatHistoryResponse)
def get_chat_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    ctx: ChatContext = Depends(get_chat_context),
) -> ChatHistoryResponse:
    conv = chat_mem.get_conversation(db, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    try:
        chat_mem.assert_conversation_access(conv, ctx)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    rows = chat_mem.load_transcript(db, conversation_id)
    return ChatHistoryResponse(
        conversation_id=conversation_id,
        messages=[
            ChatMessageIn(role=m["role"], content=m["content"])
            for m in rows
            if m.get("role") in ("user", "assistant")
        ],
    )


@public.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    emailer: EmailSender = Depends(get_emailer),
    ctx: ChatContext = Depends(get_chat_context),
) -> ChatResponse:
    msgs = [{"role": m.role, "content": m.content} for m in body.messages]
    try:
        conv_id = chat_mem.resolve_conversation_id(db, ctx, body.conversation_id)
        reply = run_chat_with_tools(msgs, db, emailer, ctx=ctx)
        full = msgs + [{"role": "assistant", "content": reply}]
        chat_mem.save_transcript(db, conv_id, full)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return ChatResponse(reply=reply, conversation_id=conv_id)


app.include_router(public)
app.include_router(api)
app.include_router(portal_auth.router, prefix="/api")
app.include_router(portal_data.router, prefix="/api")
app.include_router(data_crud.router, prefix="/api")


def _mount_frontend_spa() -> None:
    """
    When `frontend/dist` exists (after `npm run build` in `frontend/`), serve the
    Vite bundle and return index.html for client-side routes (/login, /app/...).
    """
    repo_root = Path(__file__).resolve().parent.parent
    dist = repo_root / "frontend" / "dist"
    index_html = dist / "index.html"
    if not dist.is_dir() or not index_html.is_file():
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="vite_assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(index_html)

    @app.get("/{full_path:path}")
    def spa_client_routes(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in (
            "docs",
            "redoc",
            "openapi.json",
        ):
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(index_html)


_mount_frontend_spa()
