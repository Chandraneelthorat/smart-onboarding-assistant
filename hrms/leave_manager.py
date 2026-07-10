from typing import List
from datetime import date
from sqlalchemy.orm import Session

from hrms.schemas import LeaveApplyRequest
from models import LeaveBalance, LeaveHistory


class LeaveManager:
    def __init__(self, db: Session):
        self.db = db

    def get_leave_balance(self, employee_id: str) -> str:
        """
        Return the current leave balance for an employee.
        """
        record = self.db.query(LeaveBalance).filter(LeaveBalance.emp_id == employee_id).first()
        if not record:
            return f"No leave balance record found for employee ID '{employee_id}'."
        return f"{employee_id} has {record.balance} leave day(s) remaining."

    def apply_leave(self, req: LeaveApplyRequest) -> str:
        """
        Apply leave for an employee for a list of dates.
        Deducts from balance and appends to history.
        BUG FIX: Leave dates are now always stored as Python `date` objects in the DB,
        ensuring consistency between seeded data and user-applied leaves.
        """
        balance_record = self.db.query(LeaveBalance).filter(LeaveBalance.emp_id == req.emp_id).first()
        if not balance_record:
            return f"Employee ID '{req.emp_id}' not found."

        requested = len(req.leave_dates)
        if balance_record.balance < requested:
            return (
                f"Insufficient leave balance: requested {requested}, "
                f"available {balance_record.balance}."
            )

        # Determine the next request_id for grouping this multi-day leave
        max_request = (
            self.db.query(LeaveHistory)
            .filter(LeaveHistory.emp_id == req.emp_id)
            .order_by(LeaveHistory.request_id.desc())
            .first()
        )
        next_request_id = (max_request.request_id + 1) if max_request else 1

        # Deduct balance
        balance_record.balance -= requested

        # Insert leave history rows — always store as date objects (BUG FIX)
        for leave_date in req.leave_dates:
            # leave_date comes in as a Python date from Pydantic — store directly
            entry = LeaveHistory(
                emp_id=req.emp_id,
                leave_date=leave_date if isinstance(leave_date, date) else date.fromisoformat(str(leave_date)),
                request_id=next_request_id
            )
            self.db.add(entry)

        self.db.commit()
        return (
            f"Leave applied for {requested} day(s). "
            f"Remaining balance: {balance_record.balance}."
        )

    def get_leave_history(self, employee_id: str) -> str:
        """
        Return a formatted leave history for an employee.
        BUG FIX: Previously crashed on .strftime() because some entries were ISO strings.
        Now all entries come from the DB as proper date objects — safe to format.
        """
        records: List[LeaveHistory] = (
            self.db.query(LeaveHistory)
            .filter(LeaveHistory.emp_id == employee_id)
            .order_by(LeaveHistory.leave_date)
            .all()
        )
        if not records:
            return f"No leave history found for employee ID '{employee_id}'."

        # All leave_date values are Python date objects from SQLAlchemy — safe to format
        dates = [record.leave_date.strftime("%B %d, %Y") for record in records]
        return f"Leave history for {employee_id}: {', '.join(dates)}."