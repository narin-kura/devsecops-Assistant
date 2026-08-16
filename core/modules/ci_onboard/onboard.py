"""Onboarding engine — orchestrates detection → profile → template rendering.

`onboard()` is pure compute-and-write: it takes inputs, returns a structured
`OnboardResult`, and does no printing. That keeps it callable from the CLI
*and* from an agent tool wrapper without either one fighting the other's
output. `format_report()` / `onboard_cli()` below are the CLI-only
presentation layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ...logging_utils import get_logger
from .detector import detect, ProjectProfile
from .profiles import get_profile, PipelineProfile

log = get_logger(__name__)

# Template directory lives next to this file
_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# Maps CLI CI-tool names → (template filename, default output path relative to project)
CI_TOOLS = {
    "github-actions": ("github_actions.yml.j2", ".github/workflows/ci.yml"),
    "gitlab":         ("gitlab_ci.yml.j2",      ".gitlab-ci.yml"),
    "jenkins":        ("jenkinsfile.j2",         "Jenkinsfile"),
    "azure":          ("azure_pipelines.yml.j2", "azure-pipelines.yml"),
    "bitbucket":      ("bitbucket_pipelines.yml.j2", "bitbucket-pipelines.yml"),
    "circleci":       ("circleci.yml.j2",        ".circleci/config.yml"),
}

_NEXT_STEPS = {
    "github-actions": [
        "1. Commit and push the file to your repository",
        "2. Go to GitHub → Actions tab to see the pipeline run",
        "3. Add any required secrets in Settings → Secrets & Variables → Actions",
    ],
    "gitlab": [
        "1. Commit and push .gitlab-ci.yml to your repository",
        "2. Go to GitLab → CI/CD → Pipelines to see the run",
        "3. Add any required variables in Settings → CI/CD → Variables",
    ],
    "jenkins": [
        "1. Commit the Jenkinsfile to your repository root",
        "2. Create a new Pipeline job in Jenkins pointing to your repo",
        "3. Configure credentials in Jenkins Credential Store",
    ],
    "azure": [
        "1. Commit azure-pipelines.yml to your repository",
        "2. Go to Azure DevOps → Pipelines → New Pipeline → Existing YAML",
        "3. Add service connections and variable groups as needed",
    ],
    "bitbucket": [
        "1. Commit bitbucket-pipelines.yml to your repository",
        "2. Enable Pipelines in Bitbucket → Repository settings → Pipelines",
        "3. Add any required repository variables",
    ],
    "circleci": [
        "1. Commit .circleci/config.yml to your repository",
        "2. Go to CircleCI → Set Up Project and connect your repo",
        "3. Add environment variables in Project Settings → Environment Variables",
    ],
}


@dataclass
class OnboardResult:
    """Structured outcome of an onboarding run — no printing baked in."""

    ci_tool: str
    template_file: str
    project: ProjectProfile
    pipeline: PipelineProfile
    rendered: str
    dry_run: bool
    output_path: Optional[Path] = None


def list_supported_tools() -> list[str]:
    """Return sorted list of supported CI tool identifiers."""
    return sorted(CI_TOOLS.keys())


def next_steps(ci_tool: str) -> list[str]:
    """Return the post-onboarding guidance for *ci_tool* (empty if unknown)."""
    return _NEXT_STEPS.get(ci_tool, [])


def onboard(
    project_path: str,
    ci_tool: str,
    deploy_branch: str = "main",
    output_path: Optional[str] = None,
    dry_run: bool = False,
) -> OnboardResult:
    """Run the full onboarding pipeline and return a structured result.

    1. Detect project profile
    2. Build pipeline profile with smart defaults
    3. Render CI template
    4. Write the result to disk, unless *dry_run* is set
    """
    if ci_tool not in CI_TOOLS:
        supported = ", ".join(list_supported_tools())
        raise ValueError(f"Unknown CI tool '{ci_tool}'. Supported: {supported}")

    template_file, default_output = CI_TOOLS[ci_tool]

    log.info("Scanning project at %s …", project_path)
    project = detect(project_path)

    pipeline = get_profile(project, ci_tool, deploy_branch)
    log.debug("Pipeline profile: %s", pipeline)

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    template = env.get_template(template_file)
    rendered = template.render(**pipeline.as_dict())

    result = OnboardResult(
        ci_tool=ci_tool,
        template_file=template_file,
        project=project,
        pipeline=pipeline,
        rendered=rendered,
        dry_run=dry_run,
    )

    if not dry_run:
        dest = Path(output_path) if output_path else Path(project_path) / default_output
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered, encoding="utf-8")
        result.output_path = dest

    return result


def format_report(result: OnboardResult) -> str:
    """Render a human-readable report for *result* — CLI presentation only."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║       DevSecOps Assistant — CI Onboarding           ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        "🔍 Detected project profile:",
        *result.project.summary_lines(),
        "",
    ]

    if result.dry_run:
        lines.append(f"📄 Rendered {result.ci_tool} pipeline ({result.template_file}):")
        lines.append("")
        lines.append("─" * 60)
        lines.append(result.rendered)
        lines.append("─" * 60)
    else:
        lines.append(f"✅ Pipeline written to: {result.output_path}")
        lines.append("")
        lines.append("📋 Next steps:")
        for step in next_steps(result.ci_tool):
            lines.append(f"   {step}")

    return "\n".join(lines)


def onboard_cli(args) -> int:
    """CLI entry point for the onboard subcommand."""
    try:
        result = onboard(
            project_path=args.project,
            ci_tool=args.ci,
            deploy_branch=args.deploy_branch,
            output_path=args.output,
            dry_run=args.dry_run,
        )
        print(format_report(result))
        return 0
    except Exception as exc:
        log.error("Onboarding failed: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1
