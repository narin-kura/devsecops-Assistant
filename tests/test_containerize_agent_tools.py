"""Tests for the containerization agent-tool wrappers and their registry linkage."""

from core.modules.containerize.agent_tools import (
    detect_project_for_containerization,
    generate_container_files,
)
from core.modules.registry.store import get_app


def _make_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    return tmp_path


def test_detect_project_for_containerization_registers_the_app(tmp_path):
    _make_python_project(tmp_path)

    summary = detect_project_for_containerization(str(tmp_path))

    assert "python" in summary.lower()
    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["language"] == "python"


def test_generate_container_files_writes_files_and_links_registry(tmp_path):
    _make_python_project(tmp_path)

    report = generate_container_files(str(tmp_path))

    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / ".dockerignore").exists()
    assert "Dockerfile written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["containerization"][0]["base_image"] == "python:3.12-slim"
    assert entry["containerization"][0]["compose"] is False


def test_generate_container_files_dry_run_does_not_write_or_link(tmp_path):
    _make_python_project(tmp_path)

    report = generate_container_files(str(tmp_path), dry_run=True)

    assert not (tmp_path / "Dockerfile").exists()
    assert "Rendered Dockerfile" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "containerization" not in (entry or {})


def test_generate_container_files_with_compose_links_compose_flag(tmp_path):
    _make_python_project(tmp_path)

    generate_container_files(str(tmp_path), include_compose=True)

    assert (tmp_path / "docker-compose.yml").exists()
    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["containerization"][0]["compose"] is True
