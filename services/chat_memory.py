"""Persist AI chat transcripts per portal user (or anonymous API-key sessions)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.chat_context import ChatContext
from models import ChatConversation, ChatMessage


def new_conversation_id() -> str:
    return str(uuid.uuid4())


def assert_conversation_access(conv: ChatConversation, ctx: ChatContext) -> None:
    """Same rules for read/write: portal-bound conversations belong to that portal user only."""
    if conv.portal_user_id is None:
        if ctx.portal_user_id is not None:
            raise PermissionError(
                "This conversation was started without a portal login and cannot be continued while signed in."
            )
        return
    if ctx.portal_user_id is None:
        raise PermissionError("Sign in to access this conversation.")
    if int(ctx.portal_user_id) != int(conv.portal_user_id):
        raise PermissionError("Not your conversation.")


def get_conversation(db: Session, conversation_id: str) -> Optional[ChatConversation]:
    return db.query(ChatConversation).filter(ChatConversation.id == conversation_id).first()


def create_conversation(db: Session, ctx: ChatContext) -> str:
    cid = new_conversation_id()
    row = ChatConversation(
        id=cid,
        portal_user_id=ctx.portal_user_id,
        chat_role=ctx.role,
        employee_id=ctx.employee_id,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return cid


def resolve_conversation_id(
    db: Session,
    ctx: ChatContext,
    conversation_id: Optional[str],
) -> str:
    if not conversation_id:
        return create_conversation(db, ctx)
    conv = get_conversation(db, conversation_id)
    if not conv:
        raise ValueError("Conversation not found.")
    assert_conversation_access(conv, ctx)
    return conversation_id


def load_transcript(db: Session, conversation_id: str) -> List[Dict[str, str]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.seq.asc())
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in rows]


def save_transcript(
    db: Session,
    conversation_id: str,
    messages: List[Dict[str, Any]],
) -> None:
    """Replace stored messages with the given user/assistant transcript (in order)."""
    now = datetime.now(timezone.utc)
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation_id).delete(
        synchronize_session=False
    )
    for i, m in enumerate(messages):
        role = str(m.get("role", ""))
        content = str(m.get("content", ""))
        if role not in ("user", "assistant"):
            continue
        db.add(
            ChatMessage(
                conversation_id=conversation_id,
                seq=i,
                role=role,
                content=content,
            )
        )
    db.query(ChatConversation).filter(ChatConversation.id == conversation_id).update(
        {ChatConversation.updated_at: now},
        synchronize_session=False,
    )
    db.commit()
