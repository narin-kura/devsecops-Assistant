"""Agent-tool wrappers around the CI onboarding module.

These are the tools the CI Onboarding specialist calls. Each one is a thin
wrapper around detect()/onboard() that also registers/links what it found
in the shared registry (core.modules.registry), so later specialists can
see what CI tooling an app already has without re-detecting it.
"""

from __future__ import annotations

from anthropic import beta_tool

from ..registry.store import app_id_for, link, register_app
from .detector import detect
from .onboard import format_report, list_supported_tools, onboard


@beta_tool
def detect_project(project_path: str) -> str:
    """Scan a project directory and report its detected language, framework, package manager, and tooling signals.

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
def list_ci_tools() -> str:
    """List the CI/CD tools this assistant can currently generate a pipeline for."""
    return ", ".join(list_supported_tools())


@beta_tool
def onboard_ci_pipeline(
    project_path: str,
    ci_tool: str,
    deploy_branch: str = "main",
    output_path: str = "",
    dry_run: bool = False,
) -> str:
    """Detect a project and generate a CI/CD pipeline for it, writing the file unless dry_run is set.

    Args:
        project_path: Path to the project to onboard.
        ci_tool: Target CI tool. Call list_ci_tools first if you're not sure which are supported.
        deploy_branch: Branch to deploy from.
        output_path: Explicit output file path. Leave empty to use the tool's conventional path.
        dry_run: If true, only preview the rendered pipeline without writing it to disk.
    """
    result = onboard(
        project_path=project_path,
        ci_tool=ci_tool,
        deploy_branch=deploy_branch,
        output_path=output_path or None,
        dry_run=dry_run,
    )

    app_id = app_id_for(project_path)
    register_app(
        project_path,
        app_id,
        language=result.project.language,
        framework=result.project.framework,
    )
    if not dry_run:
        link(
            project_path,
            app_id,
            "ci_cd",
            {
                "tool": ci_tool,
                "output_path": str(result.output_path),
                "deploy_branch": deploy_branch,
            },
        )

    return format_report(result)


CI_ONBOARDING_TOOLS = [detect_project, list_ci_tools, onboard_ci_pipeline]
