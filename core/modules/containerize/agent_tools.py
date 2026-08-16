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
from .k8s import DEFAULT_REPLICAS, format_report as format_k8s_report, generate_helm_chart, generate_k8s_manifests


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


@beta_tool
def generate_kubernetes_manifests(
    project_path: str,
    port: int = 0,
    replicas: int = DEFAULT_REPLICAS,
    image: str = "",
    output_dir: str = "",
    dry_run: bool = False,
) -> str:
    """Detect a project and generate a plain Kubernetes Deployment + Service manifest pair, writing files unless dry_run is set.

    Args:
        project_path: Path to the project to generate manifests for.
        port: Port the app listens on. Leave 0 to use the framework's conventional default.
        replicas: Number of pod replicas.
        image: Container image reference. Leave empty to use "<service-name>:latest" as a placeholder — the caller should override this once the real registry path is known.
        output_dir: Directory to write the manifests into. Leave empty to use "<project>/k8s".
        dry_run: If true, only preview the rendered files without writing them to disk.
    """
    result = generate_k8s_manifests(
        project_path=project_path,
        port=port or None,
        replicas=replicas,
        image=image or None,
        output_dir=output_dir or None,
        dry_run=dry_run,
    )

    app_id = app_id_for(project_path)
    register_app(project_path, app_id, language=result.container.language, framework=result.container.framework)
    if not dry_run:
        link(
            project_path,
            app_id,
            "kubernetes",
            {"kind": "manifests", "service_name": result.container.service_name, "port": result.container.port},
        )

    return format_k8s_report(result)


@beta_tool
def generate_helm_chart_files(
    project_path: str,
    port: int = 0,
    replicas: int = DEFAULT_REPLICAS,
    output_dir: str = "",
    dry_run: bool = False,
) -> str:
    """Detect a project and generate a minimal, installable Helm chart, writing files unless dry_run is set.

    Args:
        project_path: Path to the project to generate a Helm chart for.
        port: Port the app listens on. Leave 0 to use the framework's conventional default.
        replicas: Default replicaCount in values.yaml.
        output_dir: Directory to write the chart into. Leave empty to use "<project>/chart".
        dry_run: If true, only preview the rendered files without writing them to disk.
    """
    result = generate_helm_chart(
        project_path=project_path,
        port=port or None,
        replicas=replicas,
        output_dir=output_dir or None,
        dry_run=dry_run,
    )

    app_id = app_id_for(project_path)
    register_app(project_path, app_id, language=result.container.language, framework=result.container.framework)
    if not dry_run:
        link(
            project_path,
            app_id,
            "kubernetes",
            {"kind": "helm", "service_name": result.container.service_name, "port": result.container.port},
        )

    return format_k8s_report(result)


CONTAINERIZATION_TOOLS = [
    detect_project_for_containerization,
    generate_container_files,
    generate_kubernetes_manifests,
    generate_helm_chart_files,
]
