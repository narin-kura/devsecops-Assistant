"""Tests for the security-scan agent-tool wrappers and their registry linkage."""

from core.modules.registry.store import get_app
from core.modules.security_scan.agent_tools import (
    run_security_scan,
    scan_for_risky_patterns,
    scan_for_secrets,
)


def _project_with_findings(tmp_path):
    (tmp_path / "app.py").write_text(
        'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\neval(x)\n', encoding="utf-8"
    )
    return tmp_path


def test_scan_for_secrets_reports_findings(tmp_path):
    _project_with_findings(tmp_path)

    report = scan_for_secrets(str(tmp_path))

    assert "aws-access-key-id" in report


def test_scan_for_secrets_reports_clean(tmp_path):
    (tmp_path / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    report = scan_for_secrets(str(tmp_path))

    assert report == "No secrets detected."


def test_scan_for_risky_patterns_reports_findings(tmp_path):
    _project_with_findings(tmp_path)

    report = scan_for_risky_patterns(str(tmp_path))

    assert "py-eval" in report


def test_run_security_scan_does_not_write_report_by_default(tmp_path):
    _project_with_findings(tmp_path)

    report = run_security_scan(str(tmp_path), include_dependencies=False)

    assert not (tmp_path / "SECURITY_FINDINGS.md").exists()
    assert "Dry run" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert "security" not in (entry or {})


def test_run_security_scan_writes_report_and_links_registry_when_asked(tmp_path):
    _project_with_findings(tmp_path)

    report = run_security_scan(str(tmp_path), include_dependencies=False, write_findings_report=True)

    assert (tmp_path / "SECURITY_FINDINGS.md").exists()
    assert "written to" in report

    entry = get_app(str(tmp_path), tmp_path.name)
    assert entry["security"][0]["counts"]["critical"] == 1
    assert len(entry["security"][0]["finding_ids"]) >= 2


def test_run_security_scan_can_scope_to_a_single_scanner(tmp_path):
    _project_with_findings(tmp_path)

    report = run_security_scan(
        str(tmp_path), include_secrets=False, include_patterns=True, include_dependencies=False
    )

    assert "high" in report
    assert "critical" not in report
