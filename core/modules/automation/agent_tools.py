"""Agent-tool wrappers around the automation-frameworks module.

These are the tools the Automation Frameworks specialist calls. Each one is
a thin wrapper around detect()/automate() that also registers/links what it
generated in the shared registry (core.modules.registry), so later
specialists can see what dev-workflow automation a project already has.
"""

from __future__ import annotations

from anthropic import beta_tool

from ..ci_onboard.detector import detect
from ..registry.store import app_id_for, link, register_app
from .automate import ALL_TARGETS, automate, format_report


@beta_tool
def detect_project_for_automation(project_path: str) -> str:
    """Scan a project directory and report its detected language, framework, and package manager.

    Args:
        project_path: Path to the project directory to scan.
    """
    profile = detect(project_path)
    register_app(
        project_path,
        app_id_for(project_path),
        language=profile.language,
        framework=profile.framework,
        package_manager=profile.package_manager,
    )
    return "\n".join(profile.summary_lines())


@beta_tool
def list_automation_targets() -> str:
    """List the automation artifacts this assistant can currently generate."""
    return ", ".join(ALL_TARGETS)


@beta_tool
def generate_automation_files(
    project_path: str,
    targets: str = "",
    dry_run: bool = False,
) -> str:
    """Detect a project and generate automation artifacts (Makefile, Dependabot config, pre-commit config), writing files unless dry_run is set.

    Args:
        project_path: Path to the project to scaffold automation for.
        targets: Comma-separated subset of makefile,dependabot,precommit. Leave empty to generate all three.
        dry_run: If true, only preview the rendered files without writing them to disk.
    """
    target_list = [t.strip() for t in targets.split(",") if t.strip()] or None
    result = automate(project_path=project_path, targets=target_list, dry_run=dry_run)

    app_id = app_id_for(project_path)
    register_app(
        project_path,
        app_id,
        language=result.project.language,
        framework=result.project.framework,
    )
    if not dry_run and result.written_paths:
        link(
            project_path,
            app_id,
            "automation",
            {
                "targets": list(result.written_paths.keys()),
                "ecosystems": result.ecosystems,
            },
        )

    return format_report(result)


AUTOMATION_TOOLS = [detect_project_for_automation, list_automation_targets, generate_automation_files]
