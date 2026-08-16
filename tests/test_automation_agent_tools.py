"""Tests for the automation-frameworks agent-tool wrappers and their registry linkage."""

from core.modules.automation.agent_tools import (
    detect_project_for_automation,
    generate_automation_files,
    list_automation_targets,
)
from core.modules.registry.store import get_app


def _make_python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def test_detect_project_for_automation_registers_the_app(tmp_path):
    _make_python_project(tmp_path)

    summary = detect_project_for_automation(str(tmp_path))

    assert "python" in summary.lower()
    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["language"] == "python"


def test_list_automation_targets_includes_known_targets():
    targets = list_automation_targets()
    assert "makefile" in targets
    assert "dependabot" in targets
    assert "precommit" in targets


def test_generate_automation_files_writes_files_and_links_registry(tmp_path):
    _make_python_project(tmp_path)

    report = generate_automation_files(str(tmp_path))

    assert (tmp_path / "Makefile").exists()
    assert (tmp_path / ".github" / "dependabot.yml").exists()
    assert (tmp_path / ".pre-commit-config.yaml").exists()
    assert "written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert set(entry["automation"][0]["targets"]) == {"makefile", "dependabot", "precommit"}
    assert entry["automation"][0]["ecosystems"] == ["pip"]


def test_generate_automation_files_dry_run_does_not_write_or_link(tmp_path):
    _make_python_project(tmp_path)

    report = generate_automation_files(str(tmp_path), dry_run=True)

    assert not (tmp_path / "Makefile").exists()
    assert "Rendered Makefile" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "automation" not in (entry or {})


def test_generate_automation_files_honors_comma_separated_targets(tmp_path):
    _make_python_project(tmp_path)

    generate_automation_files(str(tmp_path), targets="makefile")

    assert (tmp_path / "Makefile").exists()
    assert not (tmp_path / ".github" / "dependabot.yml").exists()
    assert not (tmp_path / ".pre-commit-config.yaml").exists()


def test_generate_automation_files_does_not_link_when_everything_skipped(tmp_path):
    (tmp_path / "README.md").write_text("nothing recognizable\n", encoding="utf-8")

    generate_automation_files(str(tmp_path), targets="dependabot")

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "automation" not in (entry or {})
