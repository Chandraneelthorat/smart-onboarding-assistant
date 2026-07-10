"""Password hashing (bcrypt) compatible with bcrypt 4.x/5.x."""
from __future__ import annotations

import bcrypt


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("ascii"))
