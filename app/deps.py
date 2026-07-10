import os

from dotenv import load_dotenv

load_dotenv()

from emails import EmailSender

from database import SessionLocal, engine, Base

import models  # noqa: F401

from app.db_migrate import run_portal_migrations
from app.dev_seed_employees import seed_demo_employees_if_configured
from app.portal_seed import seed_portal_users_if_configured

Base.metadata.create_all(bind=engine)
run_portal_migrations()

_db = SessionLocal()
try:
    seed_demo_employees_if_configured(_db)
    seed_portal_users_if_configured(_db)
finally:
    _db.close()


def get_emailer() -> EmailSender:
    return EmailSender(
        smtp_server="smtp.gmail.com",
        port=587,
        username=os.getenv("CB_EMAIL"),
        password=os.getenv("CB_EMAIL_PWD"),
        use_tls=True,
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
