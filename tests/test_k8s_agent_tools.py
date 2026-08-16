"""Tests for the Kubernetes/Helm agent-tool wrappers and their registry linkage."""

from core.modules.containerize.agent_tools import (
    generate_helm_chart_files,
    generate_kubernetes_manifests,
)
from core.modules.registry.store import get_app


def _make_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    return tmp_path


def test_generate_kubernetes_manifests_writes_files_and_links_registry(tmp_path):
    _make_python_project(tmp_path)

    report = generate_kubernetes_manifests(str(tmp_path))

    assert (tmp_path / "k8s" / "deployment.yaml").exists()
    assert (tmp_path / "k8s" / "service.yaml").exists()
    assert "written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["kubernetes"][0]["kind"] == "manifests"
    assert entry["kubernetes"][0]["port"] == 5000


def test_generate_kubernetes_manifests_dry_run_does_not_write_or_link(tmp_path):
    _make_python_project(tmp_path)

    report = generate_kubernetes_manifests(str(tmp_path), dry_run=True)

    assert not (tmp_path / "k8s").exists()
    assert "Rendered deployment" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "kubernetes" not in (entry or {})


def test_generate_kubernetes_manifests_honors_explicit_image(tmp_path):
    _make_python_project(tmp_path)

    generate_kubernetes_manifests(str(tmp_path), image="ghcr.io/org/app:v1")

    content = (tmp_path / "k8s" / "deployment.yaml").read_text(encoding="utf-8")
    assert "ghcr.io/org/app:v1" in content


def test_generate_helm_chart_files_writes_files_and_links_registry(tmp_path):
    _make_python_project(tmp_path)

    report = generate_helm_chart_files(str(tmp_path))

    assert (tmp_path / "chart" / "Chart.yaml").exists()
    assert (tmp_path / "chart" / "templates" / "deployment.yaml").exists()
    assert "written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["kubernetes"][0]["kind"] == "helm"


def test_generate_helm_chart_files_dry_run_does_not_write_or_link(tmp_path):
    _make_python_project(tmp_path)

    report = generate_helm_chart_files(str(tmp_path), dry_run=True)

    assert not (tmp_path / "chart").exists()
    assert "Rendered Chart.yaml" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "kubernetes" not in (entry or {})
