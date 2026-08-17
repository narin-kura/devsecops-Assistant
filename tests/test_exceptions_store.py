"""Tests for the Exceptions Tracking store.

test_bare_date_expiry_does_not_crash_status is a direct regression: an
earlier version parsed a user-supplied expiry like "2026-12-01" (a naive
datetime) and compared it against datetime.now(timezone.utc) (aware),
which raises TypeError. Dates near the actual UTC-midnight boundary are
avoided here on purpose (a fixed clearly-future/clearly-past date instead
of "tomorrow") since the real system clock's UTC offset from local time
can otherwise make a "days from now" test flake.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core.modules.exceptions.store import (
    create_exception,
    expiring_within,
    find_waiver_for_finding,
    get_exception,
    list_exceptions,
    revoke_exception,
)

FAR_FUTURE = "2099-01-01"
FAR_PAST = "2020-01-01"


def test_create_exception_defaults_to_active(tmp_path):
    waiver = create_exception(str(tmp_path), "myapp", "desc", "why", "narin", FAR_FUTURE)

    assert waiver.status() == "active"
    assert waiver.app_id == "myapp"
    assert waiver.waiver_id


def test_bare_date_expiry_does_not_crash_status(tmp_path):
    # The exact bug class: naive vs. aware datetime comparison.
    waiver = create_exception(str(tmp_path), "myapp", "desc", "why", "narin", FAR_FUTURE)

    assert waiver.status() in {"active", "expired"}  # must not raise


def test_expired_date_is_reported_as_expired(tmp_path):
    waiver = create_exception(str(tmp_path), "myapp", "desc", "why", "narin", FAR_PAST)

    assert waiver.status() == "expired"


def test_invalid_expiry_raises_at_creation_not_later(tmp_path):
    with pytest.raises(ValueError):
        create_exception(str(tmp_path), "myapp", "desc", "why", "narin", "not-a-date")


def test_list_exceptions_filters_by_app_id_and_status(tmp_path):
    create_exception(str(tmp_path), "app-a", "d1", "w1", "narin", FAR_FUTURE)
    create_exception(str(tmp_path), "app-b", "d2", "w2", "narin", FAR_PAST)

    only_a = list_exceptions(str(tmp_path), app_id="app-a")
    assert len(only_a) == 1
    assert only_a[0].app_id == "app-a"

    only_expired = list_exceptions(str(tmp_path), status="expired")
    assert len(only_expired) == 1
    assert only_expired[0].app_id == "app-b"


def test_get_exception_by_id(tmp_path):
    created = create_exception(str(tmp_path), "myapp", "d", "w", "narin", FAR_FUTURE)

    found = get_exception(str(tmp_path), created.waiver_id)

    assert found is not None
    assert found.waiver_id == created.waiver_id


def test_get_exception_returns_none_for_unknown_id(tmp_path):
    assert get_exception(str(tmp_path), "doesnotexist") is None


def test_revoke_exception_changes_status_and_persists(tmp_path):
    created = create_exception(str(tmp_path), "myapp", "d", "w", "narin", FAR_FUTURE)

    revoked = revoke_exception(str(tmp_path), created.waiver_id, "risk materialized")

    assert revoked.status() == "revoked"
    reloaded = get_exception(str(tmp_path), created.waiver_id)
    assert reloaded.status() == "revoked"
    assert reloaded.revoked_reason == "risk materialized"


def test_revoke_unknown_id_raises_key_error(tmp_path):
    with pytest.raises(KeyError):
        revoke_exception(str(tmp_path), "doesnotexist", "reason")


def test_expiring_within_only_returns_active_waivers_in_window(tmp_path):
    near = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    far = (datetime.now(timezone.utc) + timedelta(days=365)).date().isoformat()

    create_exception(str(tmp_path), "myapp", "near", "w", "narin", near)
    create_exception(str(tmp_path), "myapp", "far", "w", "narin", far)

    soon = expiring_within(str(tmp_path), days=7)

    assert len(soon) == 1
    assert soon[0].description == "near"


def test_expiring_within_excludes_revoked_waivers(tmp_path):
    near = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
    created = create_exception(str(tmp_path), "myapp", "near", "w", "narin", near)
    revoke_exception(str(tmp_path), created.waiver_id, "no longer needed")

    assert expiring_within(str(tmp_path), days=7) == []


def test_find_waiver_for_finding_matches_active_only(tmp_path):
    create_exception(str(tmp_path), "myapp", "d", "w", "narin", FAR_FUTURE, finding_id="abc123")

    match = find_waiver_for_finding(str(tmp_path), "abc123")
    assert match is not None
    assert match.finding_id == "abc123"

    assert find_waiver_for_finding(str(tmp_path), "no-such-finding") is None


def test_find_waiver_for_finding_ignores_expired_waiver(tmp_path):
    create_exception(str(tmp_path), "myapp", "d", "w", "narin", FAR_PAST, finding_id="abc123")

    assert find_waiver_for_finding(str(tmp_path), "abc123") is None


def test_find_waiver_for_finding_ignores_revoked_waiver(tmp_path):
    created = create_exception(str(tmp_path), "myapp", "d", "w", "narin", FAR_FUTURE, finding_id="abc123")
    revoke_exception(str(tmp_path), created.waiver_id, "reason")

    assert find_waiver_for_finding(str(tmp_path), "abc123") is None


def test_store_persists_across_separate_calls(tmp_path):
    create_exception(str(tmp_path), "myapp", "d1", "w", "narin", FAR_FUTURE)
    create_exception(str(tmp_path), "myapp", "d2", "w", "narin", FAR_FUTURE)

    assert len(list_exceptions(str(tmp_path))) == 2
    assert (tmp_path / ".devsecops" / "exceptions.json").exists()
