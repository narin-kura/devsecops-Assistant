"""Unit tests for the Dependabot package-ecosystem mapping."""

from core.modules.ci_onboard.detector import ProjectProfile
from core.modules.automation.ecosystem_profiles import primary_ecosystem


def test_python_pip_maps_to_pip_ecosystem():
    assert primary_ecosystem(ProjectProfile(language="python", package_manager="pip")) == "pip"


def test_python_poetry_and_pipenv_also_map_to_pip_ecosystem():
    assert primary_ecosystem(ProjectProfile(language="python", package_manager="poetry")) == "pip"
    assert primary_ecosystem(ProjectProfile(language="python", package_manager="pipenv")) == "pip"


def test_javascript_managers_all_map_to_npm_ecosystem():
    for mgr in ("npm", "yarn", "pnpm"):
        assert primary_ecosystem(ProjectProfile(language="javascript", package_manager=mgr)) == "npm"


def test_java_maven_and_gradle_map_to_distinct_ecosystems():
    assert primary_ecosystem(ProjectProfile(language="java", package_manager="maven")) == "maven"
    assert primary_ecosystem(ProjectProfile(language="java", package_manager="gradle")) == "gradle"


def test_go_maps_to_gomod():
    assert primary_ecosystem(ProjectProfile(language="go", package_manager="go modules")) == "gomod"


def test_rust_maps_to_cargo():
    assert primary_ecosystem(ProjectProfile(language="rust", package_manager="cargo")) == "cargo"


def test_csharp_maps_to_nuget():
    assert primary_ecosystem(ProjectProfile(language="csharp", package_manager="dotnet")) == "nuget"


def test_ruby_maps_to_bundler():
    assert primary_ecosystem(ProjectProfile(language="ruby", package_manager="bundler")) == "bundler"


def test_unknown_language_has_no_ecosystem():
    assert primary_ecosystem(ProjectProfile(language="unknown", package_manager=None)) is None
