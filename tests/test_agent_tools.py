"""Tests for the CI onboarding agent-tool wrappers and their registry linkage."""

from core.modules.ci_onboard.agent_tools import (
    detect_project,
    list_ci_tools,
    onboard_ci_pipeline,
)
from core.modules.registry.store import get_app


def _make_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_detect_project_registers_the_app(tmp_path):
    _make_python_project(tmp_path)

    summary = detect_project(str(tmp_path))

    assert "python" in summary.lower()
    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["language"] == "python"
    assert entry["framework"] == "flask"


def test_list_ci_tools_includes_known_tools():
    tools = list_ci_tools()
    assert "github-actions" in tools
    assert "jenkins" in tools


def test_onboard_ci_pipeline_writes_file_and_links_registry(tmp_path):
    _make_python_project(tmp_path)

    report = onboard_ci_pipeline(str(tmp_path), ci_tool="github-actions")

    assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
    assert "Pipeline written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["ci_cd"][0]["tool"] == "github-actions"
    assert ".github" in entry["ci_cd"][0]["output_path"]


def test_onboard_ci_pipeline_dry_run_does_not_write_or_link(tmp_path):
    _make_python_project(tmp_path)

    report = onboard_ci_pipeline(str(tmp_path), ci_tool="gitlab", dry_run=True)

    assert not (tmp_path / ".gitlab-ci.yml").exists()
    assert "Rendered gitlab pipeline" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "ci_cd" not in (entry or {})
