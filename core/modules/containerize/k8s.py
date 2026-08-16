"""Kubernetes manifest and Helm chart generation — the other half of Containerization.

Reuses the same ContainerProfile (service name, port) that Dockerfile
generation builds via container_profiles.get_container_profile(), so a
project's runtime shape only needs to be inferred once.

Helm chart templates are a special case: their *output* is itself a
Go-template that Helm re-renders at install time ("{{ .Values.x }}"),
which uses the exact same "{{ }}" delimiter Jinja2 uses by default.
Rather than wrapping every Go-template expression in {% raw %} (the same
class of bug that bit templates/github_actions.yml.j2 earlier in this
project — a stray {{ language }} left outside its raw block), the two
files that must keep Go-template syntax intact are rendered through a
Jinja Environment configured with a different variable delimiter ("[[ ]]")
so "{{ }}" simply isn't special to Jinja there and passes through verbatim
by construction, not by remembering to wrap it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ...logging_utils import get_logger
from ..ci_onboard.detector import detect
from .container_profiles import ContainerProfile, get_container_profile

log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

DEFAULT_REPLICAS = 2

_K8S_MANIFEST_FILES = {
    "deployment": "k8s/deployment.yaml.j2",
    "service": "k8s/service.yaml.j2",
}

_HELM_PLAIN_FILES = {
    "Chart.yaml": "helm/Chart.yaml.j2",
    "values.yaml": "helm/values.yaml.j2",
    ".helmignore": "helm/helmignore.j2",
}

# These two render through the "[[ ]]" env — see module docstring.
_HELM_TEMPLATE_FILES = {
    "templates/deployment.yaml": "helm/templates/deployment.yaml.j2",
    "templates/service.yaml": "helm/templates/service.yaml.j2",
}


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def _helm_template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        variable_start_string="[[",
        variable_end_string="]]",
    )


@dataclass
class K8sResult:
    """Structured outcome of a K8s manifest / Helm chart run — no printing baked in."""

    container: ContainerProfile
    kind: str  # "manifests" or "helm"
    rendered: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    written_paths: Dict[str, Path] = field(default_factory=dict)


def _build_context(container: ContainerProfile, replicas: int, image: Optional[str]) -> Dict[str, object]:
    return {
        "service_name": container.service_name,
        "port": container.port,
        "replicas": replicas,
        "image": image or f"{container.service_name}:latest",
        "image_repository": container.service_name,
        "image_tag": "latest",
    }


def generate_k8s_manifests(
    project_path: str,
    port: Optional[int] = None,
    replicas: int = DEFAULT_REPLICAS,
    image: Optional[str] = None,
    output_dir: Optional[str] = None,
    dry_run: bool = False,
) -> K8sResult:
    """Detect a project and generate a plain Deployment + Service manifest pair.

    *image* defaults to "<service-name>:latest" (the name `containerize`'s
    own suggested `docker build -t` command would produce) since there's no
    way to infer a real registry path — callers should override it once
    they know where the image will actually be pushed.
    """
    project = detect(project_path)
    container = get_container_profile(project, project_path, port=port)
    ctx = _build_context(container, replicas, image)

    env = _env()
    result = K8sResult(container=container, kind="manifests", dry_run=dry_run)
    for name, template_file in _K8S_MANIFEST_FILES.items():
        result.rendered[name] = env.get_template(template_file).render(**ctx)

    if not dry_run:
        root = Path(output_dir) if output_dir else Path(project_path).resolve() / "k8s"
        root.mkdir(parents=True, exist_ok=True)
        for name, content in result.rendered.items():
            dest = root / f"{name}.yaml"
            dest.write_text(content, encoding="utf-8")
            result.written_paths[name] = dest

    return result


def generate_helm_chart(
    project_path: str,
    port: Optional[int] = None,
    replicas: int = DEFAULT_REPLICAS,
    output_dir: Optional[str] = None,
    dry_run: bool = False,
) -> K8sResult:
    """Detect a project and generate a minimal, immediately-installable Helm chart."""
    project = detect(project_path)
    container = get_container_profile(project, project_path, port=port)
    ctx = _build_context(container, replicas, image=None)

    plain_env = _env()
    helm_env = _helm_template_env()

    result = K8sResult(container=container, kind="helm", dry_run=dry_run)
    for rel_path, template_file in _HELM_PLAIN_FILES.items():
        result.rendered[rel_path] = plain_env.get_template(template_file).render(**ctx)
    for rel_path, template_file in _HELM_TEMPLATE_FILES.items():
        result.rendered[rel_path] = helm_env.get_template(template_file).render(**ctx)

    if not dry_run:
        chart_root = Path(output_dir) if output_dir else Path(project_path).resolve() / "chart"
        for rel_path, content in result.rendered.items():
            dest = chart_root / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            result.written_paths[rel_path] = dest

    return result


def format_report(result: K8sResult) -> str:
    """Render a human-readable report for *result* — CLI presentation only."""
    label = "Helm chart" if result.kind == "helm" else "Kubernetes manifests"
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        f"║   DevSecOps Assistant — {label:<29}║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        f"📦 Service     : {result.container.service_name}",
        f"🔌 Port        : {result.container.port}",
        "",
    ]

    if result.dry_run:
        for rel_path, content in result.rendered.items():
            lines.append(f"📄 Rendered {rel_path}:")
            lines.append("─" * 60)
            lines.append(content)
            lines.append("─" * 60)
            lines.append("")
    else:
        for rel_path, path in result.written_paths.items():
            lines.append(f"✅ {rel_path} written to: {path}")
        lines.append("")
        lines.append("📋 Next steps:")
        lines.append("   1. Replace the placeholder image reference with your real registry path")
        if result.kind == "helm":
            lines.append("   2. Review values.yaml, then: helm install <release> ./chart")
        else:
            lines.append("   2. Review the manifests, then: kubectl apply -f k8s/")

    return "\n".join(lines)


def k8s_cli(args) -> int:
    """CLI entry point for the k8s subcommand."""
    try:
        if args.helm:
            result = generate_helm_chart(
                project_path=args.project,
                port=args.port,
                replicas=args.replicas,
                output_dir=args.output_dir,
                dry_run=args.dry_run,
            )
        else:
            result = generate_k8s_manifests(
                project_path=args.project,
                port=args.port,
                replicas=args.replicas,
                image=args.image,
                output_dir=args.output_dir,
                dry_run=args.dry_run,
            )
        print(format_report(result))
        return 0
    except Exception as exc:
        log.error("Kubernetes/Helm generation failed: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1
