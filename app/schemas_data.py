"""Pydantic models for /api/data CRUD."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class EmployeePatchBody(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    manager_id: Optional[str] = None


class LeaveBalancePatchBody(BaseModel):
    balance: int = Field(..., ge=0)


class MeetingPatchBody(BaseModel):
    emp_id: Optional[str] = None
    meeting_dt: Optional[str] = Field(
        None, description="ISO datetime string"
    )
    topic: Optional[str] = None


class TicketFullPatchBody(BaseModel):
    item: Optional[str] = None
    reason: Optional[str] = None
    status: Optional[Literal["Open", "In Progress", "Closed", "Rejected"]] = None


class LeaveHistoryCreateBody(BaseModel):
    emp_id: str
    leave_date: str
    request_id: int = Field(..., ge=1)


class MeetingCreateDataBody(BaseModel):
    emp_id: str
    meeting_datetime: str
    topic: str


class ManagerPatchBody(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    linked_emp_id: Optional[str] = Field(
        None,
        description="HRMS employee id (E…) to link; omit or null to clear",
    )
    onboarding_status: Optional[str] = None

