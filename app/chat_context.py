"""Role context for OpenRouter tool dispatch."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatContext:
    """Who is chatting and how tool calls should be scoped."""

    role: str  # "hr" | "employee"
    portal_user_id: Optional[int] = None
    employee_id: Optional[str] = None
    """For HR users who are also employees: used as leave approver identity."""
    approver_emp_id: Optional[str] = None

    def effective_approver(self) -> Optional[str]:
        return (
            self.approver_emp_id
            or self.employee_id
            or os.getenv("HR_APPROVER_EMP_ID")
            or None
        )
