"""The concrete cross-module link between Security Scanning and Exceptions Tracking.

A finding's stable finding_id is exactly "the specific finding" a waiver
references (per ROADMAP.md). These tests verify that link actually works
end-to-end -- an active waiver against a finding_id makes that finding show
up as waived in both the CLI summary and the Markdown report, an expired
or revoked waiver does not, and a project that's never touched Exceptions
Tracking still scans cleanly (no crash just because .devsecops/exceptions.json
doesn't exist).
"""

from core.modules.exceptions.store import create_exception, revoke_exception
from core.modules.security_scan.remediation import (
    build_markdown_report,
    format_report,
    run_full_scan,
)

FAR_FUTURE = "2099-01-01"
FAR_PAST = "2020-01-01"


def _project_with_one_finding(tmp_path):
    (tmp_path / "app.py").write_text("eval(x)\n", encoding="utf-8")
    return tmp_path


def test_scan_with_no_exceptions_ever_recorded_has_no_waivers(tmp_path):
    _project_with_one_finding(tmp_path)

    result = run_full_scan(str(tmp_path), include_dependencies=False)

    assert result.waivers == {}
    assert len(result.unwaived_findings()) == 1


def test_active_waiver_marks_the_matching_finding_as_waived(tmp_path):
    _project_with_one_finding(tmp_path)
    finding_id = run_full_scan(str(tmp_path), include_dependencies=False).findings[0].finding_id

    create_exception(str(tmp_path), "myapp", "accepted", "sandboxed", "narin", FAR_FUTURE, finding_id=finding_id)

    result = run_full_scan(str(tmp_path), include_dependencies=False)

    assert finding_id in result.waivers
    assert result.unwaived_findings() == []


def test_expired_waiver_does_not_mark_finding_as_waived(tmp_path):
    _project_with_one_finding(tmp_path)
    finding_id = run_full_scan(str(tmp_path), include_dependencies=False).findings[0].finding_id

    create_exception(str(tmp_path), "myapp", "accepted", "sandboxed", "narin", FAR_PAST, finding_id=finding_id)

    result = run_full_scan(str(tmp_path), include_dependencies=False)

    assert result.waivers == {}
    assert len(result.unwaived_findings()) == 1


def test_revoked_waiver_does_not_mark_finding_as_waived(tmp_path):
    _project_with_one_finding(tmp_path)
    finding_id = run_full_scan(str(tmp_path), include_dependencies=False).findings[0].finding_id
    waiver = create_exception(str(tmp_path), "myapp", "accepted", "sandboxed", "narin", FAR_FUTURE, finding_id=finding_id)
    revoke_exception(str(tmp_path), waiver.waiver_id, "risk materialized")

    result = run_full_scan(str(tmp_path), include_dependencies=False)

    assert result.waivers == {}


def test_markdown_report_shows_waived_badge_and_justification(tmp_path):
    _project_with_one_finding(tmp_path)
    finding_id = run_full_scan(str(tmp_path), include_dependencies=False).findings[0].finding_id
    create_exception(str(tmp_path), "myapp", "accepted", "sandboxed input only", "narin", FAR_FUTURE, finding_id=finding_id)

    report = build_markdown_report(run_full_scan(str(tmp_path), include_dependencies=False))

    assert "WAIVED" in report
    assert "sandboxed input only" in report
    assert "approved by narin" in report


def test_cli_summary_shows_waived_count(tmp_path):
    _project_with_one_finding(tmp_path)
    finding_id = run_full_scan(str(tmp_path), include_dependencies=False).findings[0].finding_id
    create_exception(str(tmp_path), "myapp", "accepted", "sandboxed", "narin", FAR_FUTURE, finding_id=finding_id)

    summary = format_report(run_full_scan(str(tmp_path), include_dependencies=False))

    assert "waived" in summary
