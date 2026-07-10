"""Persistence for the separate `managers` roster (onboarding manager hires)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from models import Manager


def get_next_mgr_id(db: Session) -> str:
    ids = [row[0] for row in db.query(Manager.mgr_id).all()]
    if not ids:
        return "M001"
    numeric = []
    for mid in ids:
        if isinstance(mid, str) and len(mid) > 1 and mid[0].upper() == "M" and mid[1:].isdigit():
            numeric.append(int(mid[1:]))
    if not numeric:
        return "M001"
    return f"M{max(numeric) + 1:03d}"


def add_manager_get_id(
    db: Session,
    name: str,
    email: str | None,
    *,
    linked_emp_id: str | None = None,
) -> str:
    mgr_id = get_next_mgr_id(db)
    if db.query(Manager).filter(Manager.mgr_id == mgr_id).first():
        raise ValueError(f"Manager ID '{mgr_id}' already exists.")
    row = Manager(
        mgr_id=mgr_id,
        name=name.strip(),
        email=email.strip() if email and email.strip() else None,
        linked_emp_id=linked_emp_id.strip() if linked_emp_id and linked_emp_id.strip() else None,
        onboarding_status="Active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return mgr_id
