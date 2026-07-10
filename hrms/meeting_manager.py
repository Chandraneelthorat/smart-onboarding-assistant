from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session

from hrms.schemas import MeetingCreate, MeetingCancelRequest
from models import Meeting


class MeetingManager:
    def __init__(self, db: Session):
        self.db = db

    def schedule_meeting(self, req: MeetingCreate) -> str:
        conflict = (
            self.db.query(Meeting)
            .filter(
                Meeting.emp_id == req.emp_id,
                Meeting.meeting_dt == req.meeting_dt,
            )
            .first()
        )
        if conflict:
            raise ValueError(
                f"Conflict: {req.emp_id} already has a meeting at {req.meeting_dt.isoformat()}."
            )

        new_meeting = Meeting(
            emp_id=req.emp_id,
            meeting_dt=req.meeting_dt,
            topic=req.topic,
            hr_emp_id=getattr(req, "hr_emp_id", None),
            agenda=getattr(req, "agenda", None),
            location_or_link=getattr(req, "location_or_link", None),
            meeting_status="Scheduled",
        )
        self.db.add(new_meeting)
        self.db.commit()
        who = (req.display_participant_id or "").strip() or req.emp_id
        return (
            f"Meeting scheduled for {who} on {req.meeting_dt.isoformat()} "
            f"about '{req.topic}'."
        )

    def get_meetings(self, employee_id: str) -> List[Dict[str, str]]:
        records = (
            self.db.query(Meeting)
            .filter(Meeting.emp_id == employee_id)
            .order_by(Meeting.meeting_dt)
            .all()
        )
        out: List[Dict[str, str]] = []
        for m in records:
            out.append(
                {
                    "meeting_id": str(m.id),
                    "date": m.meeting_dt.isoformat(),
                    "topic": m.topic,
                    "title": m.topic,
                    "agenda": m.agenda or "",
                    "location_or_link": m.location_or_link or "",
                    "hr_emp_id": m.hr_emp_id or "",
                    "status": m.meeting_status or "Scheduled",
                }
            )
        return out

    def cancel_meeting(self, req: MeetingCancelRequest) -> str:
        query = self.db.query(Meeting).filter(
            Meeting.emp_id == req.emp_id,
            Meeting.meeting_dt == req.meeting_dt,
        )
        if req.topic:
            query = query.filter(Meeting.topic == req.topic)

        meeting = query.first()
        if not meeting:
            raise ValueError("No matching meeting found to cancel.")

        self.db.delete(meeting)
        self.db.commit()
        topic_str = f" about '{req.topic}'" if req.topic else ""
        return f"Canceled meeting for {req.emp_id} on {req.meeting_dt.isoformat()}{topic_str}."
