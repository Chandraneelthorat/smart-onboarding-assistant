from typing import List, Dict, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from hrms.schemas import TicketCreate, TicketStatusUpdate
from models import Ticket


def apply_closure_notice_for_status(ticket: Ticket, status: str) -> None:
    """When HR closes a ticket, employees get an in-app notice until they dismiss it."""
    ticket.closure_notify_pending = status == "Closed"


class TicketManager:
    def __init__(self, db: Session):
        self.db = db

    def _get_next_ticket_id(self) -> str:
        tickets = self.db.query(Ticket.ticket_id).all()
        if not tickets:
            return "T0001"
        max_num = max(int(t.ticket_id[1:]) for t in tickets)
        return f"T{max_num + 1:04d}"

    def create_ticket(self, req: TicketCreate) -> str:
        """Persist a new ticket; returns ``ticket_id`` (e.g. ``T0001``)."""
        ticket_id = self._get_next_ticket_id()
        now = datetime.now(timezone.utc)
        display_title = getattr(req, "title", None) or req.item

        new_ticket = Ticket(
            ticket_id=ticket_id,
            emp_id=req.emp_id,
            item=req.item,
            reason=req.reason,
            title=display_title,
            department=getattr(req, "department", None),
            created_by_emp_id=getattr(req, "created_by_emp_id", None),
            status="Open",
            created_at=now,
            updated_at=now,
        )
        self.db.add(new_ticket)
        self.db.commit()
        return ticket_id

    def update_ticket_status(self, req: TicketStatusUpdate, ticket_id: str) -> str:
        ticket = self.db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
        if not ticket:
            raise ValueError(f"Ticket '{ticket_id}' not found.")

        ticket.status = req.status
        apply_closure_notice_for_status(ticket, req.status)
        ticket.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        return f"Ticket {ticket_id} status updated to '{req.status}'."

    def list_tickets(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        query = self.db.query(Ticket)

        if employee_id:
            query = query.filter(Ticket.emp_id == employee_id)
        if status:
            query = query.filter(Ticket.status.ilike(status))

        results = query.all()
        out: List[Dict[str, str]] = []
        for t in results:
            row = {
                "ticket_id": t.ticket_id,
                "emp_id": t.emp_id,
                "item": t.item,
                "title": t.title or t.item,
                "reason": t.reason,
                "department": t.department or "",
                "status": t.status,
                "created_by": t.created_by_emp_id or "",
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            out.append(row)
        return out

    def list_pending_closure_notices(self, emp_id: str) -> List[Dict[str, str]]:
        rows = (
            self.db.query(Ticket)
            .filter(
                Ticket.emp_id == emp_id,
                Ticket.status == "Closed",
                Ticket.closure_notify_pending.is_(True),
            )
            .order_by(Ticket.updated_at.desc())
            .all()
        )
        return [
            {
                "ticket_id": t.ticket_id,
                "title": t.title or t.item,
                "item": t.item,
            }
            for t in rows
        ]

    def acknowledge_closure_notices(
        self, emp_id: str, ticket_ids: Optional[List[str]] = None
    ) -> int:
        q = self.db.query(Ticket).filter(
            Ticket.emp_id == emp_id,
            Ticket.status == "Closed",
            Ticket.closure_notify_pending.is_(True),
        )
        if ticket_ids:
            q = q.filter(Ticket.ticket_id.in_(ticket_ids))
        rows = q.all()
        for t in rows:
            t.closure_notify_pending = False
        self.db.commit()
        return len(rows)
