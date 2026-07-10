from typing import Any, Dict, List, Optional
from difflib import get_close_matches
from sqlalchemy.orm import Session

from hrms.schemas import EmployeeCreate
from models import Employee, LeaveBalance, Manager


class EmployeeManager:
    def __init__(self, db: Session):
        self.db = db

    def get_next_emp_id(self) -> str:
        """
        Generate the next employee ID based on the highest existing ID in the DB.
        """
        emp_ids = [row.emp_id for row in self.db.query(Employee.emp_id).all()]
        if not emp_ids:
            return "E001"
        max_id = max(int(eid[1:]) for eid in emp_ids)
        return f"E{max_id + 1:03d}"

    def add_employee(self, emp: EmployeeCreate) -> None:
        """
        Add a new employee to the database.
        Raises ValueError if emp_id already exists or manager_id is invalid.
        """
        if self.db.query(Employee).filter(Employee.emp_id == emp.emp_id).first():
            raise ValueError(f"Employee ID '{emp.emp_id}' already exists.")

        # Coerce empty string to None — prevents FK constraint violation for top-level managers
        resolved_manager_id = emp.manager_id if emp.manager_id else None

        if resolved_manager_id:
            manager = self.db.query(Employee).filter(Employee.emp_id == resolved_manager_id).first()
            if not manager:
                raise ValueError(f"Manager ID '{resolved_manager_id}' does not exist.")

        new_employee = Employee(
            emp_id=emp.emp_id,
            name=emp.name,
            manager_id=resolved_manager_id,
            email=emp.email,
            onboarding_status="Active",
        )
        self.db.add(new_employee)

        # Create a default leave balance record for the new employee
        leave_balance = LeaveBalance(emp_id=emp.emp_id, balance=20)
        self.db.add(leave_balance)

        self.db.commit()
        self.db.refresh(new_employee)

    def get_manager(self, emp_id: str) -> str:
        """
        Return manager's ID and name, or a message if none assigned.
        """
        emp = self.db.query(Employee).filter(Employee.emp_id == emp_id).first()
        if not emp:
            raise ValueError(f"Employee ID '{emp_id}' not found.")
        if not emp.manager_id:
            return "No manager assigned."
        mgr = self.db.query(Employee).filter(Employee.emp_id == emp.manager_id).first()
        return f"{mgr.emp_id}: {mgr.name}"

    def search_employee_by_name(self, name_query: str, n: int = 5, cutoff: float = 0.5) -> List[str]:
        """
        Fuzzy search employees by name. Returns list of matching emp_ids.

        Strategy (in order of priority):
        1. Exact case-insensitive match on full name
        2. Case-insensitive substring match (e.g. "jane" matches "Jane Dixon")
        3. Fuzzy full-name match with lowered cutoff (0.5) for typos/misspellings
        4. Token-level fuzzy match — each word in the query is matched against
           each word in every employee name (catches "Dickson" vs "Dixon")
        """
        all_employees = self.db.query(Employee).all()
        query_lower = name_query.strip().lower()
        matched_ids = []
        seen = set()

        def add(emp_id):
            if emp_id not in seen:
                seen.add(emp_id)
                matched_ids.append(emp_id)

        # 1. Exact case-insensitive full name match
        for e in all_employees:
            if e.name.lower() == query_lower:
                add(e.emp_id)

        # 2. Substring match — query is contained in name or vice versa
        for e in all_employees:
            name_lower = e.name.lower()
            if query_lower in name_lower or name_lower in query_lower:
                add(e.emp_id)

        # 3. Fuzzy full-name match
        all_names = [e.name for e in all_employees]
        fuzzy_matches = get_close_matches(name_query, all_names, n=n, cutoff=cutoff)
        for e in all_employees:
            if e.name in fuzzy_matches:
                add(e.emp_id)

        # 4. Token-level fuzzy match — split query and name into words, match each token
        query_tokens = query_lower.split()
        for e in all_employees:
            name_tokens = e.name.lower().split()
            for q_token in query_tokens:
                token_matches = get_close_matches(q_token, name_tokens, n=1, cutoff=0.7)
                if token_matches:
                    add(e.emp_id)
                    break  # one matching token is enough to include this employee

        return matched_ids[:n]

    def get_employee_details(self, emp_id: str) -> Dict[str, Any]:
        """
        Return employee details as a dictionary.

        ``manager_id`` / ``manager_name`` are the **reporting-line** manager (``employees.manager_id`` → another
        ``employees`` row). Separate from the **people-leader roster** (``managers`` table, M-prefixed ids), exposed
        as ``people_leader_mgr_id`` / ``people_leader_name`` when this employee is linked as a roster leader.
        """
        emp = self.db.query(Employee).filter(Employee.emp_id == emp_id).first()
        if not emp:
            raise ValueError(f"Employee ID '{emp_id}' not found.")
        mgr_name = ""
        if emp.manager_id:
            mgr = self.db.query(Employee).filter(Employee.emp_id == emp.manager_id).first()
            mgr_name = (mgr.name if mgr else "") or ""

        roster = self.db.query(Manager).filter(Manager.linked_emp_id == emp.emp_id).first()
        roster_mg = roster.mgr_id if roster else ""
        roster_nm = (roster.name if roster else "") or ""

        reports = (
            self.db.query(Employee)
            .filter(Employee.manager_id == emp.emp_id)
            .order_by(Employee.emp_id)
            .all()
        )
        rep_parts = [f"{r.emp_id} ({r.name})" for r in reports[:12]]
        if len(reports) > 12:
            rep_parts.append(f"+{len(reports) - 12} more")
        reports_summary = ", ".join(rep_parts)

        direct_reports: List[Dict[str, str]] = [
            {
                "emp_id": r.emp_id,
                "name": r.name,
                "email": (r.email or "").strip(),
            }
            for r in reports
        ]

        return {
            "emp_id": emp.emp_id,
            "name": emp.name,
            "manager_id": (emp.manager_id or "").strip(),
            "manager_name": mgr_name.strip(),
            "email": emp.email or "",
            "onboarding_status": getattr(emp, "onboarding_status", None) or "Active",
            "created_at": emp.created_at.isoformat() if getattr(emp, "created_at", None) else "",
            "people_leader_mgr_id": (roster_mg or "").strip(),
            "people_leader_name": roster_nm.strip(),
            "direct_reports_count": str(len(reports)),
            "direct_reports_summary": reports_summary,
            "direct_reports": direct_reports,
        }

    def get_direct_reports(self, manager_id: str) -> List[str]:
        """
        Return list of emp_ids who report to the given manager.
        """
        if not self.db.query(Employee).filter(Employee.emp_id == manager_id).first():
            raise ValueError(f"Manager ID '{manager_id}' not found.")
        reports = self.db.query(Employee).filter(Employee.manager_id == manager_id).all()
        return [e.emp_id for e in reports]