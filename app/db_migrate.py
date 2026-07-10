"""Apply additive PostgreSQL migrations for portal features (idempotent)."""
from sqlalchemy import text

from database import engine


def run_portal_migrations() -> None:
    stmts = [
        """CREATE TABLE IF NOT EXISTS managers (
            mgr_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            email VARCHAR,
            onboarding_status VARCHAR(32) DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """ALTER TABLE employees ADD COLUMN IF NOT EXISTS onboarding_status VARCHAR(32) DEFAULT 'Active'""",
        """ALTER TABLE employees ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()""",
        """ALTER TABLE tickets ADD COLUMN IF NOT EXISTS title VARCHAR(255)""",
        """ALTER TABLE tickets ADD COLUMN IF NOT EXISTS department VARCHAR(128)""",
        """ALTER TABLE tickets ADD COLUMN IF NOT EXISTS created_by_emp_id VARCHAR""",
        """ALTER TABLE tickets ADD COLUMN IF NOT EXISTS closure_notify_pending BOOLEAN NOT NULL DEFAULT FALSE""",
        """ALTER TABLE meetings ADD COLUMN IF NOT EXISTS hr_emp_id VARCHAR""",
        """ALTER TABLE meetings ADD COLUMN IF NOT EXISTS agenda TEXT""",
        """ALTER TABLE meetings ADD COLUMN IF NOT EXISTS location_or_link VARCHAR(512)""",
        """ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_status VARCHAR(32) DEFAULT 'Scheduled'""",
        """ALTER TABLE managers ADD COLUMN IF NOT EXISTS linked_emp_id VARCHAR REFERENCES employees(emp_id)""",
    ]
    with engine.connect() as conn:
        for s in stmts:
            conn.execute(text(s))
        conn.commit()
