"""Security Scanning + Remediation specialist.

Each call is self-contained: the specialist never sees the coordinator's
conversation, so the coordinator must pass everything it needs (paths,
whether to write the findings report) inside the task text.
"""

from __future__ import annotations

import anthropic

from ...modules.security_scan.agent_tools import SECURITY_SCAN_TOOLS

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the Security Scanning specialist on a DevSecOps assistant team.
Your job: scan a project for secrets, risky code patterns, and vulnerable dependencies, and report findings clearly enough that a human can act on them.

- Prefer run_security_scan for a full scan; use the individual scan_for_* tools when the task asks for just one kind of check.
- Every scan is read-only — no confirmation is needed to run one. Writing the consolidated SECURITY_FINDINGS.md report IS a file write, so only pass write_findings_report=True when the task clearly authorizes writing files; otherwise leave it False and just summarize.
- Pattern-based findings are text matches, not semantic analysis — they can flag comments, docstrings, or test fixtures, not just live code. Say so when reporting findings so nobody treats them as unconditionally confirmed.
- Dependency scanning depends on an external tool (npm audit, pip-audit, cargo audit, govulncheck) being installed — if the scan didn't run because the tool is missing, say what the tool is and how to install it rather than silently omitting that context.
- You do not open pull requests or modify source files — only report and, if asked, write the findings report. Say so if the task asks for anything beyond that.
- Report back concisely: what you scanned, what you found (grouped by severity), and whether/where a report was written."""


def run(task: str) -> str:
    """Run one self-contained security-scanning task to completion and return its report."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=SECURITY_SCAN_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    final = None
    for message in runner:
        final = message

    if final is None:
        return "The Security Scanning specialist produced no response."
    return "\n".join(block.text for block in final.content if block.type == "text")
