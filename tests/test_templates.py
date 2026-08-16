"""Regression coverage: every CI tool's template must render valid output.

This would have caught the earlier GitHub Actions bug where a Jinja
variable got swallowed by a {% raw %} block — parsing the rendered output
as YAML (or checking it's non-empty for the Jenkinsfile, which is Groovy,
not YAML) catches that class of mistake generically across every tool
instead of relying on someone noticing it by eye.
"""

import yaml
import pytest

from core.modules.ci_onboard.onboard import CI_TOOLS, onboard

YAML_TOOLS = sorted(tool for tool in CI_TOOLS if tool != "jenkins")


@pytest.fixture
def full_signal_project(tmp_path):
    """A synthetic project that exercises every optional template branch."""
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / ".flake8").write_text("", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("ci_tool", YAML_TOOLS)
def test_yaml_ci_tools_render_parseable_yaml(full_signal_project, ci_tool):
    result = onboard(project_path=str(full_signal_project), ci_tool=ci_tool, dry_run=True)
    parsed = yaml.safe_load(result.rendered)
    assert parsed


def test_jenkinsfile_renders_nonempty_groovy(full_signal_project):
    # Groovy, not YAML — just check it actually produced a pipeline body.
    result = onboard(project_path=str(full_signal_project), ci_tool="jenkins", dry_run=True)
    assert "pipeline" in result.rendered.lower()
    assert result.rendered.strip()


@pytest.mark.parametrize("ci_tool", sorted(CI_TOOLS))
def test_minimal_signal_project_still_renders(tmp_path, ci_tool):
    # No tests, no lint config, no docker, no recognized framework —
    # the "detected almost nothing" case every template must still handle.
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    result = onboard(project_path=str(tmp_path), ci_tool=ci_tool, dry_run=True)
    assert result.rendered.strip()


def test_harness_cache_key_language_is_interpolated(full_signal_project):
    # The bug class this file guards against, made concrete for Harness:
    # a stray literal "{{ language }}" in the output means Jinja didn't
    # substitute it.
    result = onboard(project_path=str(full_signal_project), ci_tool="harness", dry_run=True)
    assert "{{" not in result.rendered
    assert "}}" not in result.rendered
