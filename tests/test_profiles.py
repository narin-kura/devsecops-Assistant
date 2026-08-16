"""Tests for core.modules.ci_onboard.profiles."""

from core.modules.ci_onboard.detector import ProjectProfile
from core.modules.ci_onboard.profiles import get_profile


def test_python_pip_profile_defaults():
    project = ProjectProfile(
        language="python",
        package_manager="pip",
        has_tests=True,
        has_lint_config=False,
    )

    pipeline = get_profile(project, ci_tool="github-actions", deploy_branch="main")

    assert pipeline.ci_tool == "github-actions"
    assert pipeline.docker_image == "python:3.12"
    assert pipeline.install_cmd == "pip install --upgrade pip && pip install -r requirements.txt"
    assert pipeline.test_cmd == "pytest --tb=short -q"
    # Lint command is only populated when the project actually has lint config.
    assert pipeline.lint_cmd == ""
    assert pipeline.has_security_scan is True


def test_javascript_npm_profile_uses_language_defaults():
    project = ProjectProfile(language="javascript", package_manager="npm", has_tests=True)

    pipeline = get_profile(project, ci_tool="circleci")

    assert pipeline.docker_image == "node:20"
    assert pipeline.install_cmd == "npm ci"
    assert pipeline.test_cmd == "npm test"
    assert pipeline.cache_paths == ["node_modules", ".npm"]


def test_test_cmd_omitted_when_project_has_no_tests():
    project = ProjectProfile(language="python", package_manager="pip", has_tests=False)

    pipeline = get_profile(project, ci_tool="jenkins")

    assert pipeline.test_cmd == ""
    assert pipeline.has_tests is False


def test_lint_cmd_included_when_project_has_lint_config():
    project = ProjectProfile(language="python", package_manager="pip", has_lint_config=True)

    pipeline = get_profile(project, ci_tool="gitlab")

    assert pipeline.lint_cmd == "ruff check . || flake8 ."
    assert pipeline.has_lint is True


def test_unknown_language_returns_safe_empty_defaults():
    project = ProjectProfile(language="unknown")

    pipeline = get_profile(project, ci_tool="azure")

    assert pipeline.docker_image == ""
    assert pipeline.install_cmd == ""
    assert pipeline.build_cmd == ""
    assert pipeline.cache_paths == []


def test_java_uses_package_manager_specific_command_maps():
    maven_project = ProjectProfile(language="java", package_manager="maven", has_tests=True)
    gradle_project = ProjectProfile(language="java", package_manager="gradle", has_tests=True)

    maven_pipeline = get_profile(maven_project, ci_tool="bitbucket")
    gradle_pipeline = get_profile(gradle_project, ci_tool="bitbucket")

    assert maven_pipeline.build_cmd == "mvn package -DskipTests"
    assert maven_pipeline.test_cmd == "mvn test"
    assert gradle_pipeline.build_cmd == "./gradlew build -x test"
    assert gradle_pipeline.test_cmd == "./gradlew test"


def test_deploy_branch_passthrough():
    project = ProjectProfile(language="go", package_manager="go modules")

    pipeline = get_profile(project, ci_tool="github-actions", deploy_branch="release")

    assert pipeline.deploy_branch == "release"


def test_runtime_version_falls_back_to_language_default():
    project = ProjectProfile(language="python", package_manager="pip", runtime_version=None)

    pipeline = get_profile(project, ci_tool="github-actions")

    assert pipeline.runtime_version == "3.12"
    assert pipeline.docker_image == "python:3.12"


def test_runtime_version_from_project_overrides_default():
    project = ProjectProfile(language="python", package_manager="pip", runtime_version="3.11")

    pipeline = get_profile(project, ci_tool="github-actions")

    assert pipeline.runtime_version == "3.11"
    assert pipeline.docker_image == "python:3.11"
