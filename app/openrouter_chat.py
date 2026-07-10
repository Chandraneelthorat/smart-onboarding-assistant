"""
OpenRouter chat with tool-calling loop (OpenAI-compatible API).
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.chat_context import ChatContext
from app.openai_tools import system_prompt_for_role, tools_for_role
from app.tool_dispatch import dispatch_tool
from emails import EmailSender

MAX_TOOL_ITERATIONS = 8


def _plain_chat_response(text: str) -> str:
    """Strip Markdown bold and hyphen/asterisk list markers for UI that renders plain text."""
    if not text:
        return text
    s = text.replace("**", "")
    lines: List[str] = []
    for line in s.splitlines():
        m = re.match(r"^(\s*)-\s+(.*)$", line)
        if m:
            lines.append(m.group(1) + m.group(2))
            continue
        m = re.match(r"^(\s*)\*\s+(.*)$", line)
        if m:
            lines.append(m.group(1) + m.group(2))
            continue
        lines.append(line)
    return "\n".join(lines).rstrip()


def _client() -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return OpenAI(
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=key,
        default_headers={
            "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost"),
            "X-Title": os.getenv("OPENROUTER_TITLE", "HR-ASSIST"),
        },
    )


def run_chat_with_tools(
    messages: List[Dict[str, Any]],
    db: Session,
    emailer: EmailSender,
    ctx: Optional[ChatContext] = None,
    model: Optional[str] = None,
) -> str:
    """
    messages: OpenAI-format chat messages (no system required; one will be prepended).
    Returns assistant text reply.
    """
    ctx = ctx or ChatContext(role="hr")
    model = model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    client = _client()
    tool_list = tools_for_role(ctx.role)
    system = system_prompt_for_role(ctx.role)

    api_messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    for m in messages:
        if m.get("role") in ("user", "assistant", "tool", "system"):
            api_messages.append({k: v for k, v in m.items() if v is not None})

    for _ in range(MAX_TOOL_ITERATIONS):
        resp = client.chat.completions.create(
            model=model,
            messages=api_messages,
            tools=tool_list,
            tool_choice="auto",
        )
        choice = resp.choices[0]
        msg = choice.message

        if msg.tool_calls:
            api_messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = dispatch_tool(tc.function.name, args, db, emailer, ctx)
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )
            continue

        text = (msg.content or "").strip()
        if text:
            return _plain_chat_response(text)
        return "(No text response from model.)"

    return "Stopped: too many tool rounds (safety limit)."
