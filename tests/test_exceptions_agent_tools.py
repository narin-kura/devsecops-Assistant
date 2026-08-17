"""Tests for the Exceptions Tracking agent-tool wrappers."""

from core.modules.exceptions.agent_tools import (
    check_expiring_exceptions,
    list_project_exceptions,
    record_exception,
    revoke_project_exception,
)

FAR_FUTURE = "2099-01-01"


def test_record_exception_reports_id_and_expiry(tmp_path):
    report = record_exception(str(tmp_path), "desc", "why", "narin", FAR_FUTURE)

    assert "Recorded exception" in report
    assert FAR_FUTURE in report


def test_record_exception_with_finding_id_links_it(tmp_path):
    record_exception(str(tmp_path), "desc", "why", "narin", FAR_FUTURE, finding_id="abc123")

    report = list_project_exceptions(str(tmp_path))

    assert "abc123" in report


def test_list_project_exceptions_reports_none_when_empty(tmp_path):
    report = list_project_exceptions(str(tmp_path))

    assert "No exceptions recorded" in report


def test_list_project_exceptions_filters_by_status(tmp_path):
    record_exception(str(tmp_path), "active one", "why", "narin", FAR_FUTURE)
    record_exception(str(tmp_path), "past one", "why", "narin", "2020-01-01")

    active_only = list_project_exceptions(str(tmp_path), status="active")

    assert "active one" in active_only
    assert "past one" not in active_only


def test_revoke_project_exception_by_id(tmp_path):
    record_exception(str(tmp_path), "desc", "why", "narin", FAR_FUTURE)
    listing = list_project_exceptions(str(tmp_path))
    waiver_id = listing.split()[1].rstrip(",")

    report = revoke_project_exception(str(tmp_path), waiver_id, "no longer needed")

    assert "Revoked exception" in report
    assert "revoked" in list_project_exceptions(str(tmp_path))


def test_revoke_project_exception_unknown_id_reports_error_not_crash(tmp_path):
    report = revoke_project_exception(str(tmp_path), "doesnotexist", "reason")

    assert "No exception found" in report


def test_check_expiring_exceptions_reports_none_by_default(tmp_path):
    record_exception(str(tmp_path), "desc", "why", "narin", FAR_FUTURE)

    report = check_expiring_exceptions(str(tmp_path), within_days=7)

    assert "No active exceptions" in report
