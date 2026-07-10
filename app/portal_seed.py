"""Optional portal user seed from environment (dev/demo)."""
from __future__ import annotations

import os
import warnings

from sqlalchemy.orm import Session

from app.passwords import hash_password
from models import Employee, PortalUser


def seed_portal_users_if_configured(db: Session) -> None:
    hr_email = os.getenv("PORTAL_HR_EMAIL")
    hr_password = os.getenv("PORTAL_HR_PASSWORD")
    emp_email = os.getenv("PORTAL_EMP_EMAIL")
    emp_password = os.getenv("PORTAL_EMP_PASSWORD")
    emp_id = os.getenv("PORTAL_EMP_EMP_ID")

    def _employee_row_exists(eid: str | None) -> bool:
        if eid is None or not str(eid).strip():
            return True
        return (
            db.query(Employee).filter(Employee.emp_id == str(eid).strip()).first() is not None
        )

    def _ensure(email: str, password: str, role: str, employee_id: str | None) -> None:
        if db.query(PortalUser).filter(PortalUser.email == email.lower()).first():
            return
        db.add(
            PortalUser(
                email=email.lower(),
                password_hash=hash_password(password),
                role=role,
                employee_id=employee_id,
                is_active=True,
            )
        )
        db.commit()

    if hr_email and hr_password:
        hr_emp = os.getenv("PORTAL_HR_EMP_ID") or None
        if hr_emp and not _employee_row_exists(hr_emp):
            warnings.warn(
                f"Skipping PORTAL_HR_* seed: employee_id {hr_emp!r} is not in the employees table.",
                stacklevel=1,
            )
        else:
            _ensure(hr_email, hr_password, "hr", hr_emp)
    if emp_email and emp_password and emp_id:
        eid = str(emp_id).strip()
        if not _employee_row_exists(eid):
            warnings.warn(
                f"Skipping PORTAL_EMP_* seed: employee_id {eid!r} is not in the employees table "
                "(add employees first, or set HR_SEED_DEMO_EMPLOYEES=1 and restart).",
                stacklevel=1,
            )
        else:
            _ensure(emp_email, emp_password, "employee", eid)
