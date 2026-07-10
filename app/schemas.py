from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EmployeeCreateBody(BaseModel):
    emp_name: str
    email: Optional[str] = Field(
        None,
        description="Work email; omit to auto-set first.last@atom.com from emp_name (Atom).",
    )
    manager_id: Optional[str] = None
    create_portal_login: bool = False
    initial_password: Optional[str] = Field(
        None,
        description="Optional portal password (min 8 characters if provided)",
    )

    @model_validator(mode="after")
    def resolve_work_email(self) -> "EmployeeCreateBody":
        from hrms.atom_email import ensure_atom_work_email

        self.email = ensure_atom_work_email(self.emp_name, self.email)
        return self


class OnboardingRunBody(BaseModel):
    employee_name: str = Field(..., min_length=1)
    employee_email: Optional[str] = Field(
        None,
        description="Work email; omit to auto-set first.last@atom.com from employee_name (Atom).",
    )
    manager_mgr_id: Optional[str] = Field(
        None,
        description="People-manager roster id (M-prefixed, e.g. M001). Preferred when is_manager_hire is false.",
    )
    manager_name: Optional[str] = Field(
        None,
        description="Legacy: resolve reporting manager by employee name if manager_mgr_id is omitted.",
    )
    is_manager_hire: bool = Field(
        False,
        description=(
            "If true, run people-manager hire: linked employees + managers roster row, tickets, and meeting. "
            "Portal credentials are returned in the API response for HR to share (no welcome email to the hire)."
        ),
    )
    meeting_datetime: Optional[str] = None
    meeting_topic: str = "Introduction and onboarding kickoff"
    hr_emp_id: Optional[str] = Field(
        None,
        description="HR staff emp_id for meeting host / ticket created_by",
    )
    initial_portal_password: Optional[str] = Field(
        None,
        description="Optional employee portal password (min 8 chars); omit to auto-generate",
    )

    @field_validator("initial_portal_password")
    @classmethod
    def strip_portal_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if len(s) < 8:
            raise ValueError("initial_portal_password must be at least 8 characters when provided")
        return s

    @model_validator(mode="after")
    def resolve_email_and_manager_ref(self) -> "OnboardingRunBody":
        from hrms.atom_email import ensure_atom_work_email

        self.employee_email = ensure_atom_work_email(self.employee_name, self.employee_email)
        if self.is_manager_hire:
            return self
        mid = (self.manager_mgr_id or "").strip()
        mn = (self.manager_name or "").strip()
        if not mid and not mn:
            raise ValueError("Provide manager_mgr_id or manager_name when is_manager_hire is false.")
        return self


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Send full transcript each turn; optional conversation_id ties to persisted thread."""

    messages: List[ChatMessageIn] = Field(..., min_length=1)
    conversation_id: Optional[str] = Field(
        None,
        description="UUID from prior ChatResponse; omit to start a new persisted conversation",
    )


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str = Field(
        ...,
        description="Persist this ID and send on the next request for continuous memory",
    )


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[ChatMessageIn]


class MessageResponse(BaseModel):
    message: str


class LeaveApplyBody(BaseModel):
    emp_id: str = Field(..., min_length=1)
    leave_dates: List[str] = Field(..., min_length=1, description="ISO dates YYYY-MM-DD")


class LeaveRequestSubmitBody(BaseModel):
    emp_id: str = Field(..., min_length=1)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    reason: str = Field(..., min_length=1)
    message: Optional[str] = None


class ScheduleMeetingBody(BaseModel):
    employee_id: str
    meeting_datetime: str = Field(
        ...,
        description="ISO datetime e.g. 2026-04-08T10:00:00",
    )
    topic: str
    hr_emp_id: Optional[str] = None
    agenda: Optional[str] = None
    location_or_link: Optional[str] = None


class CancelMeetingBody(BaseModel):
    employee_id: str
    meeting_datetime: str
    topic: Optional[str] = None


class CreateTicketBody(BaseModel):
    emp_id: str
    item: str
    reason: str
    title: Optional[str] = None
    department: Optional[str] = None
    created_by_emp_id: Optional[str] = None


TicketStatus = Literal["Open", "In Progress", "Closed", "Rejected"]


class UpdateTicketBody(BaseModel):
    status: TicketStatus


class SendEmailBody(BaseModel):
    to_emails: List[str] = Field(..., min_length=1)
    subject: str
    body: str
    html: bool = False


class ErrorResponse(BaseModel):
    detail: str
