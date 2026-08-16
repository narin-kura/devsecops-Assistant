"""Unit tests for the container smart-default profile builder."""

from core.modules.ci_onboard.detector import ProjectProfile
from core.modules.containerize.container_profiles import get_container_profile


def test_python_flask_uses_flask_run_and_its_port(tmp_path):
    project = ProjectProfile(language="python", framework="flask", package_manager="pip")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.base_image == "python:3.12-slim"
    assert profile.multi_stage is False
    assert profile.run_cmd == ["flask", "run", "--host=0.0.0.0", "--port=5000"]
    assert profile.port == 5000


def test_python_plain_pip_falls_back_to_default_run_cmd(tmp_path):
    project = ProjectProfile(language="python", framework=None, package_manager="pip")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.run_cmd == ["python", "app.py"]
    assert profile.port == 8000
    assert profile.manifest_files == ["requirements.txt"]


def test_explicit_port_overrides_framework_default(tmp_path):
    project = ProjectProfile(language="python", framework="flask", package_manager="pip")

    profile = get_container_profile(project, str(tmp_path), port=9999)

    assert profile.port == 9999
    assert "--port=9999" in profile.run_cmd


def test_typescript_installs_full_deps_and_builds(tmp_path):
    project = ProjectProfile(language="typescript", framework=None, package_manager="npm")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.install_cmd == "npm ci"
    assert profile.build_cmd == "npm run build"
    assert profile.run_cmd == ["node", "dist/index.js"]


def test_java_maven_is_multi_stage_with_jar_copy(tmp_path):
    project = ProjectProfile(language="java", framework=None, package_manager="maven")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.multi_stage is True
    assert profile.builder_image == "eclipse-temurin:21-jdk"
    assert profile.base_image == "eclipse-temurin:21-jre"
    assert profile.build_copy_from == "/app/target/*.jar"
    assert profile.run_cmd == ["java", "-jar", "/app/app.jar"]
    assert profile.port == 8080


def test_java_gradle_uses_gradle_build_output(tmp_path):
    project = ProjectProfile(language="java", framework=None, package_manager="gradle")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.build_copy_from == "/app/build/libs/*.jar"
    assert "settings.gradle*" in profile.manifest_files


def test_go_is_multi_stage_with_fixed_binary_output(tmp_path):
    project = ProjectProfile(language="go", framework=None, package_manager="go modules")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.multi_stage is True
    assert profile.builder_image == "golang:1.22"
    assert profile.build_copy_from == "/out/app"
    assert profile.run_cmd == ["/app/app"]
    assert "go.sum*" in profile.manifest_files


def test_rust_binary_name_parsed_from_cargo_toml(tmp_path):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "my-service"\n', encoding="utf-8")
    project = ProjectProfile(language="rust", framework=None, package_manager="cargo")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.build_copy_from == "/app/target/release/my-service"


def test_rust_falls_back_to_directory_name_without_cargo_toml(tmp_path):
    project_dir = tmp_path / "fallback-service"
    project_dir.mkdir()
    project = ProjectProfile(language="rust", framework=None, package_manager="cargo")

    profile = get_container_profile(project, str(project_dir))

    assert profile.build_copy_from == "/app/target/release/fallback-service"


def test_csharp_assembly_name_parsed_from_csproj(tmp_path):
    (tmp_path / "Widget.Api.csproj").write_text("<Project />", encoding="utf-8")
    project = ProjectProfile(language="csharp", framework=None, package_manager="dotnet")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.multi_stage is True
    assert profile.run_cmd == ["dotnet", "Widget.Api.dll"]


def test_ruby_rails_uses_rails_server_command(tmp_path):
    project = ProjectProfile(language="ruby", framework="rails", package_manager="bundler")

    profile = get_container_profile(project, str(tmp_path))

    assert profile.run_cmd == ["bin/rails", "server", "-b", "0.0.0.0", "-p", "3000"]
    assert profile.port == 3000


def test_unknown_language_falls_back_to_generic_profile(tmp_path):
    project = ProjectProfile(language="unknown", framework=None, package_manager=None)

    profile = get_container_profile(project, str(tmp_path))

    assert profile.base_image == "debian:bookworm-slim"
    assert profile.multi_stage is False
    assert profile.run_cmd  # non-empty placeholder, never crashes
    assert profile.port == 8080


def test_service_name_is_slugified_from_directory_name(tmp_path):
    project_dir = tmp_path / "My_Cool App!"
    project_dir.mkdir()
    project = ProjectProfile(language="python", framework=None, package_manager="pip")

    profile = get_container_profile(project, str(project_dir))

    assert profile.service_name == "my-cool-app"
