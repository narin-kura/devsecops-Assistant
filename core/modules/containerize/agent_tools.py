"""Agent-tool wrappers around the containerization module.

These are the tools the Containerization specialist calls. Each one is a
thin wrapper around detect()/containerize() that also registers/links what
it found in the shared registry (core.modules.registry), so later
specialists (Infra, Cloud Platform, ...) can see what a project already has
containerized without re-detecting it.
"""

from __future__ import annotations

from anthropic import beta_tool

from ..ci_onboard.detector import detect
from ..registry.store import app_id_for, link, register_app
from .containerize import containerize, format_report


@beta_tool
def detect_project_for_containerization(project_path: str) -> str:
    """Scan a project directory and report its detected language, framework, package manager, and whether it already has Docker files.

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
def generate_container_files(
    project_path: str,
    port: int = 0,
    output_path: str = "",
    include_compose: bool = False,
    dry_run: bool = False,
) -> str:
    """Detect a project and generate a Dockerfile plus .dockerignore (and optionally docker-compose.yml), writing files unless dry_run is set.

    Args:
        project_path: Path to the project to containerize.
        port: Port the app listens on. Leave 0 to use the framework's conventional default.
        output_path: Explicit Dockerfile output path. Leave empty to use "<project>/Dockerfile".
        include_compose: If true, also generate a docker-compose.yml alongside the Dockerfile.
        dry_run: If true, only preview the rendered files without writing them to disk.
    """
    result = containerize(
        project_path=project_path,
        port=port or None,
        output_path=output_path or None,
        include_compose=include_compose,
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
            "containerization",
            {
                "base_image": result.container.base_image,
                "port": result.container.port,
                "dockerfile_path": str(result.dockerfile_path),
                "compose": bool(result.compose_path),
            },
        )

    return format_report(result)


CONTAINERIZATION_TOOLS = [detect_project_for_containerization, generate_container_files]
