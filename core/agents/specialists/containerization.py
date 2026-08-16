"""Containerization specialist — Dockerfiles, .dockerignore, and docker-compose.

Each call is self-contained: the specialist never sees the coordinator's
conversation, so the coordinator must pass everything it needs (paths,
port, whether to write) inside the task text. Mirrors ci_onboarding.py's
shape.
"""

from __future__ import annotations

import anthropic

from ...modules.containerize.agent_tools import CONTAINERIZATION_TOOLS

MODEL_ID = "claude-opus-5"
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are the Containerization specialist on a DevSecOps assistant team.
Your job: given a project, detect what it is and generate the artifacts needed to run it in a container — a Dockerfile (plus .dockerignore, and a docker-compose.yml when asked for one), and, when asked, Kubernetes manifests or a Helm chart to run it on a cluster.

- Always call detect_project_for_containerization before generating anything, so your output is grounded in what's actually in the project, not a guess.
- If the task doesn't clearly authorize writing files, default to dry_run so you preview before writing.
- If the task doesn't specify a port, leave it unset — the tools fall back to the detected framework's conventional default.
- For Kubernetes: use generate_kubernetes_manifests for plain Deployment/Service YAML, or generate_helm_chart_files when the task asks for a Helm chart. Both use a placeholder "<service-name>:latest" image reference unless the task gives you a real registry path — say so in your report so it isn't missed.
- Report back concisely: what you detected, what you generated, and the files you wrote (or would write)."""


def run(task: str) -> str:
    """Run one self-contained containerization task to completion and return its report."""
    client = anthropic.Anthropic()
    runner = client.beta.messages.tool_runner(
        model=MODEL_ID,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=CONTAINERIZATION_TOOLS,
        messages=[{"role": "user", "content": task}],
    )

    final = None
    for message in runner:
        final = message

    if final is None:
        return "The Containerization specialist produced no response."
    return "\n".join(block.text for block in final.content if block.type == "text")
