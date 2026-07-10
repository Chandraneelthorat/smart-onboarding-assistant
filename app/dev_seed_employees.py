"""Optional dev/demo employees when the database is empty (see HR_SEED_DEMO_EMPLOYEES)."""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from hrms import tools_impl as ti


def seed_demo_employees_if_configured(db: Session) -> None:
    """
    If HR_SEED_DEMO_EMPLOYEES is truthy and `employees` has no rows, insert a small
    hierarchy so the Data console and PORTAL_* employee logins have valid FK targets.
    """
    raw = (os.getenv("HR_SEED_DEMO_EMPLOYEES") or "").strip().lower()
    if raw not in ("1", "true", "yes", "on"):
        return

    from models import Employee

    if db.query(Employee).first() is not None:
        return

    ti.add_employee_impl(
        db,
        "Demo Lead",
        "lead.demo@local.test",
        manager_id=None,
        create_portal_login=False,
    )
    ti.add_employee_impl(
        db,
        "Demo Employee",
        "emp.demo@local.test",
        manager_id="E001",
        create_portal_login=False,
    )
