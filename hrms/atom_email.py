"""Atom company work email: first.last@atom.com from full name (matches onboarding wizard)."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

ATOM_EMAIL_DOMAIN = "atom.com"


def _strip_combining_marks(s: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )


def _sanitize_local(raw: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _strip_combining_marks(raw).lower())


def atom_work_email_from_full_name(full_name: str, domain: str = ATOM_EMAIL_DOMAIN) -> str:
    words = [w for w in full_name.strip().split() if w]
    if not words:
        return ""
    if len(words) == 1:
        local = _sanitize_local(words[0])
        return f"{local}@{domain}" if local else ""
    first = _sanitize_local(words[0])
    last = _sanitize_local(words[-1])
    if not first and not last:
        return ""
    if not last:
        return f"{first}@{domain}"
    if not first:
        return f"{last}@{domain}"
    return f"{first}.{last}@{domain}"


def ensure_atom_work_email(full_name: str, email: Optional[str] = None) -> str:
    """Use explicit work email when provided; otherwise derive first.last@atom.com from full_name."""
    s = (email or "").strip()
    if s:
        return s
    out = atom_work_email_from_full_name(full_name)
    if not out:
        raise ValueError(
            "Work email is missing and could not be derived from the employee name "
            "(add letters to the name or pass email explicitly)."
        )
    return out
