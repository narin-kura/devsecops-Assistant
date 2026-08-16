"""Automation Frameworks specialist — Makefile, Dependabot, and pre-commit scaffolding.

Each call is self-contained: the specialist never sees the coordinator's
conversation, so the coordinator must pass everything it needs (paths,
which artifacts, whether to write) inside the task text. Mirrors
containerization.py's shape.
"""

from __future__ import annotations

import anthropic

from ...modules.automation.agent_tools import AUTOMATION_TOOLS

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the Automation Frameworks specialist on a DevSecOps assistant team.
Your job: given a project, detect what it is and generate the recurring dev-workflow automation it needs — a Makefile for common commands (install/build/test/lint/clean), a Dependabot config to keep dependencies (and CI/Docker base images) updated on a schedule, and a pre-commit config to run lint/test before every commit.

- Always call detect_project_for_automation before generate_automation_files, so your output is grounded in what's actually in the project, not a guess.
- If the task doesn't say which artifacts to generate, call list_automation_targets and generate all of them unless the task narrows it down.
- If the task doesn't clearly authorize writing files, default to dry_run so you preview before writing.
- A Dependabot config may come back skipped if the project has no recognizable dependency ecosystem, Dockerfile, or CI workflow to point it at — that's expected behavior, not an error; mention it if it happens.
- Report back concisely: what you detected, what you generated, and the files you wrote (or would write)."""


def run(task: str) -> str:
    """Run one self-contained automation-scaffolding task to completion and return its report."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=AUTOMATION_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    final = None
    for message in runner:
        final = message

    if final is None:
        return "The Automation Frameworks specialist produced no response."
    return "\n".join(block.text for block in final.content if block.type == "text")
