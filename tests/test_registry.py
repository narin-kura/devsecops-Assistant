"""Tests for core.modules.registry.store."""

from core.modules.registry.store import app_id_for, get_app, link, list_apps, register_app


def test_app_id_derived_from_directory_name(tmp_path):
    project = tmp_path / "my-service"
    project.mkdir()
    assert app_id_for(str(project)) == "my-service"


def test_register_app_creates_and_updates_entry(tmp_path):
    register_app(str(tmp_path), "demo", language="python")
    entry = get_app(str(tmp_path), "demo")

    assert entry["language"] == "python"
    assert "updated_at" in entry

    register_app(str(tmp_path), "demo", framework="flask")
    entry = get_app(str(tmp_path), "demo")

    # Second call merges fields rather than replacing the entry.
    assert entry["language"] == "python"
    assert entry["framework"] == "flask"


def test_link_accumulates_domain_entries_as_a_list(tmp_path):
    register_app(str(tmp_path), "demo", language="python")

    link(str(tmp_path), "demo", "ci_cd", {"tool": "github-actions"})
    link(str(tmp_path), "demo", "ci_cd", {"tool": "circleci"})

    entry = get_app(str(tmp_path), "demo")
    tools = [item["tool"] for item in entry["ci_cd"]]

    assert tools == ["github-actions", "circleci"]
    assert all("recorded_at" in item for item in entry["ci_cd"])


def test_get_app_returns_none_for_unknown_app(tmp_path):
    assert get_app(str(tmp_path), "nonexistent") is None


def test_list_apps_returns_sorted_ids(tmp_path):
    register_app(str(tmp_path), "zeta", language="go")
    register_app(str(tmp_path), "alpha", language="rust")

    assert list_apps(str(tmp_path)) == ["alpha", "zeta"]


def test_registry_persists_to_disk_under_dot_devsecops(tmp_path):
    register_app(str(tmp_path), "demo", language="python")

    registry_file = tmp_path / ".devsecops" / "registry.json"
    assert registry_file.exists()
