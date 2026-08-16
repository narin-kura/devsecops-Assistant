"""Automation-frameworks engine — orchestrates detection -> dev-workflow scaffolding.

Generates the recurring "automation" artifacts every project eventually
needs: a Makefile for common dev commands, a Dependabot config to keep
dependencies (and CI/Docker) updated on a schedule, and a pre-commit config
to run lint/test before every commit. Mirrors ci_onboard/onboard.py and
containerize/containerize.py's shape: pure compute-and-write, no printing,
so the same function is callable from the CLI and from an agent tool
wrapper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ...logging_utils import get_logger
from ..ci_onboard.detector import detect, ProjectProfile
from ..ci_onboard.profiles import get_profile, PipelineProfile
from .ecosystem_profiles import primary_ecosystem

log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

ALL_TARGETS = ("makefile", "dependabot", "precommit")

_TEMPLATE_FILES = {
    "makefile": "Makefile.j2",
    "dependabot": "dependabot.yml.j2",
    "precommit": "pre-commit-config.yaml.j2",
}

_DEFAULT_OUTPUT_PATHS = {
    "makefile": "Makefile",
    "dependabot": ".github/dependabot.yml",
    "precommit": ".pre-commit-config.yaml",
}


@dataclass
class AutomationResult:
    """Structured outcome of an automation-scaffolding run — no printing baked in."""

    project: ProjectProfile
    pipeline: PipelineProfile
    ecosystems: List[str]
    rendered: Dict[str, str] = field(default_factory=dict)
    skipped: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    written_paths: Dict[str, Path] = field(default_factory=dict)


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def _detect_ecosystems(project: ProjectProfile, root: Path) -> List[str]:
    ecosystems = []
    eco = primary_ecosystem(project)
    if eco:
        ecosystems.append(eco)
    if (root / "Dockerfile").exists():
        ecosystems.append("docker")
    workflows_dir = root / ".github" / "workflows"
    if workflows_dir.is_dir() and any(workflows_dir.iterdir()):
        ecosystems.append("github-actions")
    return ecosystems


def automate(
    project_path: str,
    targets: Optional[List[str]] = None,
    dry_run: bool = False,
) -> AutomationResult:
    """Detect a project and generate the requested automation artifacts.

    1. Detect project profile
    2. Build the pipeline profile (install/build/test/lint commands) via the
       same smart defaults CI onboarding uses
    3. Render each requested target (Makefile, Dependabot config, pre-commit
       config) — "dependabot" is skipped (not an error) if no dependency
       ecosystem, Docker, or CI workflow was detected to point it at
    4. Write results to disk, unless *dry_run* is set
    """
    targets = list(targets) if targets else list(ALL_TARGETS)
    unknown = set(targets) - set(ALL_TARGETS)
    if unknown:
        raise ValueError(
            f"Unknown automation target(s): {', '.join(sorted(unknown))}. Supported: {', '.join(ALL_TARGETS)}"
        )

    log.info("Scanning project at %s for automation scaffolding…", project_path)
    project = detect(project_path)
    pipeline = get_profile(project, ci_tool="automation", deploy_branch="main")
    root = Path(project_path).resolve()
    ecosystems = _detect_ecosystems(project, root)

    env = _env()
    result = AutomationResult(
        project=project,
        pipeline=pipeline,
        ecosystems=ecosystems,
        dry_run=dry_run,
    )

    for target in targets:
        if target == "dependabot" and not ecosystems:
            result.skipped["dependabot"] = "no dependency ecosystem, Dockerfile, or CI workflow detected"
            continue
        template = env.get_template(_TEMPLATE_FILES[target])
        if target == "dependabot":
            result.rendered[target] = template.render(ecosystems=ecosystems)
        else:
            result.rendered[target] = template.render(**pipeline.as_dict())

    if not dry_run:
        for target, content in result.rendered.items():
            dest = root / _DEFAULT_OUTPUT_PATHS[target]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            result.written_paths[target] = dest

    return result


def format_report(result: AutomationResult) -> str:
    """Render a human-readable report for *result* — CLI presentation only."""
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║   DevSecOps Assistant — Automation Frameworks        ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        "🔍 Detected project profile:",
        *result.project.summary_lines(),
        "",
    ]
    if result.ecosystems:
        lines.append(f"📦 Dependency ecosystems: {', '.join(result.ecosystems)}")
        lines.append("")

    if result.dry_run:
        for target, content in result.rendered.items():
            lines.append(f"📄 Rendered {_DEFAULT_OUTPUT_PATHS[target]}:")
            lines.append("─" * 60)
            lines.append(content)
            lines.append("─" * 60)
            lines.append("")
    else:
        for target, path in result.written_paths.items():
            lines.append(f"✅ {target} written to: {path}")
        lines.append("")
        lines.append("📋 Next steps:")
        if "precommit" in result.written_paths:
            lines.append("   - Run `pre-commit install` to activate the git hook")
        if "dependabot" in result.written_paths:
            lines.append("   - Dependabot will open update PRs on its weekly schedule once this is pushed")
        if "makefile" in result.written_paths:
            lines.append("   - Try `make install`, `make test`, etc.")

    for target, reason in result.skipped.items():
        lines.append(f"⏭️  Skipped {target}: {reason}")

    return "\n".join(lines)


def automate_cli(args) -> int:
    """CLI entry point for the automate subcommand."""
    try:
        targets = args.targets if args.targets else None
        result = automate(project_path=args.project, targets=targets, dry_run=args.dry_run)
        print(format_report(result))
        return 0
    except Exception as exc:
        log.error("Automation scaffolding failed: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1
