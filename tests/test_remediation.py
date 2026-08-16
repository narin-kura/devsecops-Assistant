"""Tests for the security-scan aggregator and Markdown remediation report."""

from core.modules.security_scan.dependency_scan import DependencyScanOutcome
from core.modules.security_scan.findings import Finding
from core.modules.security_scan.remediation import (
    SecurityScanResult,
    build_markdown_report,
    format_report,
    run_full_scan,
    write_report,
)


def test_run_full_scan_aggregates_and_sorts_by_severity(tmp_path):
    (tmp_path / "app.py").write_text(
        'password = "harmlessplaceholder"\n'  # low, secret
        "eval(x)\n",  # high, pattern
        encoding="utf-8",
    )

    result = run_full_scan(str(tmp_path), include_dependencies=False)

    assert [f.severity for f in result.findings] == ["high", "low"]


def test_counts_by_severity(tmp_path):
    result = SecurityScanResult(
        project_path=str(tmp_path),
        findings=[
            Finding(category="secret", severity="critical", rule_id="x", message="m"),
            Finding(category="pattern", severity="high", rule_id="y", message="m"),
            Finding(category="pattern", severity="high", rule_id="z", message="m"),
        ],
    )

    counts = result.counts_by_severity()

    assert counts["critical"] == 1
    assert counts["high"] == 2
    assert counts["low"] == 0


def test_markdown_report_includes_every_finding_and_no_full_secret(tmp_path):
    result = SecurityScanResult(
        project_path=str(tmp_path),
        findings=[
            Finding(
                category="secret", severity="critical", rule_id="aws-access-key-id",
                message="AWS key found.", file="a.py", line=3, snippet="AKIA****MNOP",
            ),
        ],
    )

    report = build_markdown_report(result)

    assert "aws-access-key-id" in report
    assert "a.py:3" in report
    assert "AKIA****MNOP" in report
    assert "does not open pull requests" in report


def test_markdown_report_with_no_findings_says_so(tmp_path):
    result = SecurityScanResult(project_path=str(tmp_path), findings=[])

    report = build_markdown_report(result)

    assert "No findings." in report


def test_markdown_report_notes_when_dependency_scan_did_not_run(tmp_path):
    result = SecurityScanResult(
        project_path=str(tmp_path),
        findings=[],
        dependency_outcome=DependencyScanOutcome(
            ecosystem="pip", tool_used="pip-audit", ran=False, note="pip-audit not found on PATH."
        ),
    )

    report = build_markdown_report(result)

    assert "pip-audit not found on PATH" in report


def test_write_report_writes_to_default_and_custom_path(tmp_path):
    result = SecurityScanResult(project_path=str(tmp_path), findings=[])

    write_report(result)
    assert (tmp_path / "SECURITY_FINDINGS.md").exists()

    custom = tmp_path / "reports" / "custom.md"
    write_report(result, str(custom))
    assert custom.exists()
    assert result.report_path == custom


def test_cli_format_report_dry_run_lists_findings_without_writing():
    result = SecurityScanResult(
        project_path="/tmp/proj",
        findings=[Finding(category="secret", severity="high", rule_id="x", message="m", file="a.py", line=1)],
        dry_run=True,
    )

    summary = format_report(result)

    assert "x @ a.py:1" in summary
    assert result.report_path is None
