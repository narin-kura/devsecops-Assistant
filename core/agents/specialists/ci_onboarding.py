"""CI Onboarding specialist — first entry in the coordinator's roster.

Each call is self-contained: the specialist never sees the coordinator's
conversation, so the coordinator must pass everything it needs (paths, tool
names, constraints) inside the task text. This mirrors how a real delegated
task briefing has to work once you can't assume shared context.
"""

from __future__ import annotations

import anthropic

from ...modules.ci_onboard.agent_tools import CI_ONBOARDING_TOOLS

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the CI Onboarding specialist on a DevSecOps assistant team.
Your job: given a project, detect what it is and generate a working CI/CD pipeline for it.

- Always call detect_project before onboard_ci_pipeline, so your recommendation is grounded in what's actually in the project, not a guess.
- If the task doesn't say which CI tool to use, call list_ci_tools and pick the one the task most plausibly implies, or say what you need to know rather than guessing at random.
- If the task doesn't clearly authorize writing files, default to dry_run so you preview before writing.
- Report back concisely: what you detected, what you did, and the file you wrote (or would write)."""


def run(task: str) -> str:
    """Run one self-contained onboarding task to completion and return its report."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=CI_ONBOARDING_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    final = None
    for message in runner:
        final = message

    if final is None:
        return "The CI Onboarding specialist produced no response."
    return "\n".join(block.text for block in final.content if block.type == "text")
