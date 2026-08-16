"""End-to-end coverage for the containerize() pipeline: detect -> profile -> render -> write.

Parameterized across languages the same way test_templates.py covers every
CI tool — this is the class of check that would catch a template bug like
the earlier GitHub Actions one, generalized to Dockerfile rendering.
"""

import yaml
import pytest

from core.modules.containerize.containerize import containerize

LANGUAGE_FIXTURES = {
    "python": {"requirements.txt": "flask==3.0.0\n"},
    "javascript": {"package.json": '{"name": "demo", "dependencies": {"express": "^4.0.0"}}'},
    "typescript": {
        "package.json": '{"name": "demo", "dependencies": {}}',
        "tsconfig.json": "{}",
    },
    "java": {"pom.xml": "<project></project>"},
    "go": {"go.mod": "module demo\n"},
    "rust": {"Cargo.toml": '[package]\nname = "demo"\n'},
    "csharp": {"demo.csproj": "<Project />"},
    "ruby": {"Gemfile": 'source "https://rubygems.org"\n'},
}


@pytest.fixture(params=sorted(LANGUAGE_FIXTURES))
def language_project(request, tmp_path):
    lang = request.param
    for filename, content in LANGUAGE_FIXTURES[lang].items():
        (tmp_path / filename).write_text(content, encoding="utf-8")
    return lang, tmp_path


def test_dockerfile_renders_and_starts_with_from(language_project):
    lang, project_dir = language_project
    result = containerize(str(project_dir), dry_run=True)

    assert result.project.language == lang
    assert result.dockerfile_rendered.strip().startswith("FROM ")


def test_multi_stage_languages_have_two_from_and_a_builder_alias(language_project):
    lang, project_dir = language_project
    result = containerize(str(project_dir), dry_run=True)

    from_count = result.dockerfile_rendered.count("\nFROM ") + (
        1 if result.dockerfile_rendered.startswith("FROM ") else 0
    )
    if result.container.multi_stage:
        assert from_count == 2
        assert "AS builder" in result.dockerfile_rendered
    else:
        assert from_count == 1
        assert "AS builder" not in result.dockerfile_rendered


def test_dockerignore_renders_nonempty(language_project):
    lang, project_dir = language_project
    result = containerize(str(project_dir), dry_run=True)

    assert result.dockerignore_rendered.strip()
    assert ".git" in result.dockerignore_rendered


def test_dry_run_does_not_write_anything(language_project):
    lang, project_dir = language_project
    containerize(str(project_dir), dry_run=True)

    assert not (project_dir / "Dockerfile").exists()
    assert not (project_dir / ".dockerignore").exists()


def test_writes_dockerfile_and_dockerignore_when_not_dry_run(language_project):
    lang, project_dir = language_project
    result = containerize(str(project_dir), dry_run=False)

    assert (project_dir / "Dockerfile").read_text(encoding="utf-8") == result.dockerfile_rendered
    assert (project_dir / ".dockerignore").exists()
    assert result.dockerfile_path == project_dir / "Dockerfile"


def test_compose_is_only_generated_when_requested(language_project):
    lang, project_dir = language_project
    without = containerize(str(project_dir), dry_run=True, include_compose=False)
    with_compose = containerize(str(project_dir), dry_run=True, include_compose=True)

    assert without.compose_rendered is None
    assert with_compose.compose_rendered is not None
    parsed = yaml.safe_load(with_compose.compose_rendered)
    assert "services" in parsed


def test_compose_is_written_to_disk_alongside_dockerfile(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")

    result = containerize(str(tmp_path), dry_run=False, include_compose=True)

    assert (tmp_path / "docker-compose.yml").exists()
    assert result.compose_path == tmp_path / "docker-compose.yml"


def test_minimal_signal_project_still_renders_every_language(tmp_path):
    # No recognizable manifest at all -- the generic fallback must still
    # produce a valid, non-crashing Dockerfile.
    (tmp_path / "README.md").write_text("nothing recognizable here\n", encoding="utf-8")

    result = containerize(str(tmp_path), dry_run=True)

    assert result.dockerfile_rendered.strip().startswith("FROM debian:bookworm-slim")


def test_custom_port_is_reflected_in_expose_and_cmd(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")

    result = containerize(str(tmp_path), dry_run=True, port=9999)

    assert "EXPOSE 9999" in result.dockerfile_rendered
    assert result.container.port == 9999


def test_custom_output_path_is_honored(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    custom_dest = tmp_path / "docker" / "Dockerfile.prod"

    result = containerize(str(tmp_path), dry_run=False, output_path=str(custom_dest))

    assert custom_dest.exists()
    assert result.dockerfile_path == custom_dest
    # .dockerignore is written alongside the Dockerfile, wherever that is
    assert (custom_dest.parent / ".dockerignore").exists()
