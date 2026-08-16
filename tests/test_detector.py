"""Tests for core.modules.ci_onboard.detector."""

import pytest

from core.modules.ci_onboard.detector import detect


def test_detect_missing_directory_raises(tmp_path):
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        detect(str(missing))


def test_detect_empty_directory_is_unknown(tmp_path):
    profile = detect(str(tmp_path))
    assert profile.language == "unknown"
    assert profile.has_docker is False


def test_detect_python_pip_project(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    profile = detect(str(tmp_path))

    assert profile.language == "python"
    assert profile.package_manager == "pip"
    assert profile.framework == "flask"
    assert profile.has_tests is True


def test_detect_python_prefers_poetry_when_declared(tmp_path):
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[tool.poetry]\nname = \"demo\"\n", encoding="utf-8"
    )

    profile = detect(str(tmp_path))

    assert profile.language == "python"
    assert profile.package_manager == "poetry"


def test_detect_node_react_project_with_yarn(tmp_path):
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"react": "^18.0.0"}, "scripts": {"test": "jest"}}',
        encoding="utf-8",
    )

    profile = detect(str(tmp_path))

    assert profile.language == "javascript"
    assert profile.package_manager == "yarn"
    assert profile.framework == "react"
    assert profile.has_tests is True


def test_detect_node_typescript_project(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")

    profile = detect(str(tmp_path))

    assert profile.language == "typescript"
    assert profile.package_manager == "npm"


def test_detect_go_project_with_tests(tmp_path):
    (tmp_path / "go.mod").write_text("module demo\n", encoding="utf-8")
    (tmp_path / "main_test.go").write_text("package main\n", encoding="utf-8")

    profile = detect(str(tmp_path))

    assert profile.language == "go"
    assert profile.package_manager == "go modules"
    assert profile.has_tests is True


def test_detect_docker_is_language_independent(tmp_path):
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")

    profile = detect(str(tmp_path))

    assert profile.has_docker is True


def test_detect_first_matching_language_wins(tmp_path):
    # Python is checked before Node in _DETECTORS — both marker files present,
    # so the profile should come back Python, not JavaScript.
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    profile = detect(str(tmp_path))

    assert profile.language == "python"
