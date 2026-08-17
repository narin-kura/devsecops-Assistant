"""Exceptions Tracking specialist — system of record for accepted security risks.

Each call is self-contained: the specialist never sees the coordinator's
conversation, so the coordinator must pass everything it needs (paths,
description, justification, who approved it, expiry) inside the task text.
"""

from __future__ import annotations

import anthropic

from ...modules.exceptions.agent_tools import EXCEPTIONS_TRACKING_TOOLS

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the Exceptions Tracking specialist on a DevSecOps assistant team.
Your job: keep a system of record for accepted security risks (waivers/exceptions) — what was accepted, why, by whom, and when it expires — and surface which ones are expiring soon.

- Every exception needs description, justification, approved_by, and expires_at — if the task is missing one of these, ask for it rather than inventing a value. Never invent an approver or a justification.
- Every exception must have an expiry date. If the task says "no expiry" or "permanent", push back: an accepted risk with no review date is how it quietly becomes permanent — ask for a concrete future date instead (a year out is a reasonable default to suggest if the task has no opinion).
- If the task references a specific Security Scanning finding (a finding_id, or "the SQL injection finding from the scan"), pass that finding_id so the exception links to it — that's what lets the security report show it's already been reviewed and accepted.
- Report back concisely: what was recorded (or listed, or revoked), and its id."""


def run(task: str) -> str:
    """Run one self-contained exceptions-tracking task to completion and return its report."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=EXCEPTIONS_TRACKING_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    final = None
    for message in runner:
        final = message

    if final is None:
        return "The Exceptions Tracking specialist produced no response."
    return "\n".join(block.text for block in final.content if block.type == "text")
