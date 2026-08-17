"""Coordinator agent — the entry point for the chat surface.

Delegates to specialists rather than doing domain work itself. Keeps the
conversation with the user across turns by mirroring message history back
into each new tool_runner call (the runner doesn't persist history for you
between separate invocations).
"""

from __future__ import annotations

import anthropic
from anthropic import beta_tool

from .specialists import automation, ci_onboarding, containerization, exceptions_tracking, security_scanning

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the coordinator of a DevSecOps assistant team \
— a small group of specialist agents, each responsible for one part of a \
project's DevOps/DevSecOps lifecycle. Specialists currently on the roster:
- CI Onboarding: detects a project and generates its CI/CD pipeline.
- Containerization: detects a project and generates a Dockerfile, \
.dockerignore, optionally a docker-compose.yml, and — on request — \
Kubernetes manifests or a Helm chart to run it on a cluster.
- Automation Frameworks: detects a project and generates a Makefile, \
Dependabot config, and pre-commit config for it.
- Security Scanning: scans a project for hardcoded secrets, risky code \
patterns, and vulnerable dependencies, and can write a consolidated \
findings report. Read-only — it never opens pull requests or modifies \
source.
- Exceptions Tracking: records accepted-risk waivers (what was accepted, \
why, by whom, when it expires) and reports which are expiring soon. Can \
link a waiver to a specific Security Scanning finding_id, which then \
shows as waived in that specialist's reports.
More will be added over time.

Talk to the user like a helpful, direct teammate. Ask a clarifying \
question before delegating when something load-bearing is missing — which \
project directory, which CI tool — rather than guessing. When you do \
delegate, the specialist does not see this conversation: write its task as \
a complete, self-contained instruction (paths, tool names, constraints, \
and whether to write the file or just preview it)."""


@beta_tool
def delegate_to_ci_onboarding(task: str) -> str:
    """Hand a CI/CD onboarding task to the CI Onboarding specialist.

    Args:
        task: A complete, self-contained description of the task. Include the
            project path, the target CI tool if known, and whether to write
            the file or just preview it — the specialist does not see this
            conversation, only this task text.
    """
    return ci_onboarding.run(task)


@beta_tool
def delegate_to_containerization(task: str) -> str:
    """Hand a Dockerfile/containerization task to the Containerization specialist.

    Args:
        task: A complete, self-contained description of the task. Include the
            project path, the port if known, whether a docker-compose.yml is
            wanted, and whether to write the files or just preview them — the
            specialist does not see this conversation, only this task text.
    """
    return containerization.run(task)


@beta_tool
def delegate_to_automation(task: str) -> str:
    """Hand a dev-workflow automation task (Makefile, Dependabot, pre-commit) to the Automation Frameworks specialist.

    Args:
        task: A complete, self-contained description of the task. Include the
            project path, which artifacts are wanted (or all of them), and
            whether to write the files or just preview them — the specialist
            does not see this conversation, only this task text.
    """
    return automation.run(task)


@beta_tool
def delegate_to_security_scanning(task: str) -> str:
    """Hand a security-scanning task (secrets, risky patterns, vulnerable dependencies) to the Security Scanning specialist.

    Args:
        task: A complete, self-contained description of the task. Include the
            project path, which scan types are wanted (or all of them), and
            whether to write the SECURITY_FINDINGS.md report — the specialist
            does not see this conversation, only this task text.
    """
    return security_scanning.run(task)


@beta_tool
def delegate_to_exceptions_tracking(task: str) -> str:
    """Hand an accepted-risk / waiver task to the Exceptions Tracking specialist.

    Args:
        task: A complete, self-contained description of the task. For
            recording an exception, include the project path, what's being
            accepted, why, who approved it, when it expires, and the
            Security Scanning finding_id if this waives a specific finding —
            the specialist does not see this conversation, only this task
            text.
    """
    return exceptions_tracking.run(task)


TOOLS = [
    delegate_to_ci_onboarding,
    delegate_to_containerization,
    delegate_to_automation,
    delegate_to_security_scanning,
    delegate_to_exceptions_tracking,
]


def _print_message(message) -> None:
    for block in message.content:
        if block.type == "text" and block.text:
            print(block.text)
        elif block.type == "tool_use":
            print(f"  → delegating to {block.name}: {block.input}")


def send_turn(client: anthropic.Anthropic, messages: list, user_text: str):
    """Send one user turn, mirroring the full exchange (incl. tool calls) into *messages*."""
    messages.append({"role": "user", "content": user_text})
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=TOOLS,
        messages=messages,
    )

    final = None
    for message in runner:
        final = message
        _print_message(message)
        messages.append({"role": "assistant", "content": message.content})
        tool_response = runner.generate_tool_call_response()
        if tool_response is not None:
            messages.append(tool_response)

    return final


def repl() -> int:
    """Interactive terminal chat loop with the coordinator."""
    print("DevSecOps Assistant — chat with the coordinator. Type 'exit' to quit.\n")

    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # e.g. no credentials configured
        print(f"Could not start the chat session: {exc}")
        print("Set ANTHROPIC_API_KEY, or run `ant auth login`, and try again.")
        return 1

    messages: list = []
    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            return 0

        try:
            final = send_turn(client, messages, user_text)
        except TypeError as exc:
            # The SDK raises a plain TypeError (not AuthenticationError) when
            # no credential source is configured at all — before any request
            # is sent, so it never reaches the AuthenticationError branch below.
            if "authentication" in str(exc).lower():
                print("No API credentials found. Set ANTHROPIC_API_KEY, or run `ant auth login`, and try again.")
                return 1
            raise
        except anthropic.AuthenticationError:
            print("Authentication failed — set ANTHROPIC_API_KEY or run `ant auth login`.")
            return 1
        except anthropic.APIError as exc:
            print(f"[error] {exc}")
            continue

        if final is None:
            print("(no response)")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(repl())
