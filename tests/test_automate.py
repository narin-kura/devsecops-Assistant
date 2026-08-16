"""End-to-end coverage for the automate() pipeline: detect -> profile -> render -> write."""

import yaml
import pytest

from core.modules.automation.automate import ALL_TARGETS, automate


def _python_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / ".flake8").write_text("", encoding="utf-8")
    return tmp_path


def test_default_targets_are_all_three():
    result = automate(".", dry_run=True)
    assert set(result.rendered) | set(result.skipped) == set(ALL_TARGETS)


def test_makefile_renders_real_tabs_and_matching_targets(tmp_path):
    _python_project(tmp_path)
    result = automate(str(tmp_path), targets=["makefile"], dry_run=True)

    makefile = result.rendered["makefile"]
    assert "\tpip install" in makefile
    assert "\tpytest" in makefile
    assert ".PHONY: install test lint clean" in makefile


def test_dependabot_renders_valid_yaml_with_detected_ecosystem(tmp_path):
    _python_project(tmp_path)
    result = automate(str(tmp_path), targets=["dependabot"], dry_run=True)

    parsed = yaml.safe_load(result.rendered["dependabot"])
    ecosystems = [u["package-ecosystem"] for u in parsed["updates"]]
    assert ecosystems == ["pip"]


def test_dependabot_also_covers_docker_and_github_actions_when_present(tmp_path):
    _python_project(tmp_path)
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: ci\n", encoding="utf-8")

    result = automate(str(tmp_path), targets=["dependabot"], dry_run=True)

    parsed = yaml.safe_load(result.rendered["dependabot"])
    ecosystems = {u["package-ecosystem"] for u in parsed["updates"]}
    assert ecosystems == {"pip", "docker", "github-actions"}


def test_dependabot_is_skipped_not_errored_with_no_detected_ecosystem(tmp_path):
    (tmp_path / "README.md").write_text("nothing recognizable\n", encoding="utf-8")

    result = automate(str(tmp_path), dry_run=True)

    assert "dependabot" not in result.rendered
    assert "dependabot" in result.skipped


def test_precommit_always_has_baseline_hooks_plus_local_when_detected(tmp_path):
    _python_project(tmp_path)
    result = automate(str(tmp_path), targets=["precommit"], dry_run=True)

    parsed = yaml.safe_load(result.rendered["precommit"])
    assert parsed["repos"][0]["repo"] == "https://github.com/pre-commit/pre-commit-hooks"
    local_hooks = parsed["repos"][1]["hooks"]
    assert {h["id"] for h in local_hooks} == {"lint", "test"}


def test_precommit_has_only_baseline_hooks_with_no_lint_or_test_detected(tmp_path):
    (tmp_path / "README.md").write_text("nothing recognizable\n", encoding="utf-8")

    result = automate(str(tmp_path), targets=["precommit"], dry_run=True)

    parsed = yaml.safe_load(result.rendered["precommit"])
    assert len(parsed["repos"]) == 1


def test_dry_run_does_not_write_anything(tmp_path):
    _python_project(tmp_path)
    automate(str(tmp_path), dry_run=True)

    assert not (tmp_path / "Makefile").exists()
    assert not (tmp_path / ".github" / "dependabot.yml").exists()
    assert not (tmp_path / ".pre-commit-config.yaml").exists()


def test_writes_all_requested_targets_when_not_dry_run(tmp_path):
    _python_project(tmp_path)
    result = automate(str(tmp_path), dry_run=False)

    assert (tmp_path / "Makefile").read_text(encoding="utf-8") == result.rendered["makefile"]
    assert (tmp_path / ".github" / "dependabot.yml").exists()
    assert (tmp_path / ".pre-commit-config.yaml").exists()
    assert set(result.written_paths) == {"makefile", "dependabot", "precommit"}


def test_unknown_target_raises_value_error(tmp_path):
    _python_project(tmp_path)
    with pytest.raises(ValueError):
        automate(str(tmp_path), targets=["not-a-real-target"])


def test_minimal_signal_project_still_renders_makefile_and_precommit(tmp_path):
    (tmp_path / "README.md").write_text("nothing recognizable\n", encoding="utf-8")

    result = automate(str(tmp_path), dry_run=True)

    assert result.rendered["makefile"].strip()
    assert result.rendered["precommit"].strip()
