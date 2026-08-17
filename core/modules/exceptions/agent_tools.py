"""Agent-tool wrappers around the Exceptions Tracking store.

Every waiver is scoped to an app_id, the same identifier the shared
registry uses (core.modules.registry.store.app_id_for) — kept consistent
so a waiver naturally lines up with everything else recorded about the
same app, without needing its own separate ID scheme.
"""

from __future__ import annotations

from anthropic import beta_tool

from ..registry.store import app_id_for
from .store import create_exception, expiring_within, list_exceptions, revoke_exception


def _format_waiver(w) -> str:
    finding_part = f", finding {w.finding_id}" if w.finding_id else ""
    return (
        f"[{w.status()}] {w.waiver_id}{finding_part} — {w.description} "
        f"(approved by {w.approved_by}, expires {w.expires_at})"
    )


@beta_tool
def record_exception(
    project_path: str,
    description: str,
    justification: str,
    approved_by: str,
    expires_at: str,
    finding_id: str = "",
) -> str:
    """Record an accepted risk / waiver for a project.

    Args:
        project_path: Path to the project this exception applies to.
        description: What is being accepted (e.g. "known lodash prototype pollution CVE").
        justification: Why it's acceptable (e.g. "internal tool, no untrusted input reaches this path").
        approved_by: Who approved the exception.
        expires_at: ISO date/datetime the exception expires, e.g. "2026-12-01". Every exception must have an expiry — never accept a risk permanently without a review date.
        finding_id: The specific Security Scanning finding_id this waives, if any. Leave empty for a general exception not tied to one scan finding.
    """
    app_id = app_id_for(project_path)
    waiver = create_exception(
        project_path,
        app_id=app_id,
        description=description,
        justification=justification,
        approved_by=approved_by,
        expires_at=expires_at,
        finding_id=finding_id or None,
    )
    return f"Recorded exception {waiver.waiver_id} for {app_id}, expires {waiver.expires_at}."


@beta_tool
def list_project_exceptions(project_path: str, status: str = "") -> str:
    """List recorded exceptions for a project.

    Args:
        project_path: Path to the project.
        status: Filter to "active", "expired", or "revoked". Leave empty for all.
    """
    app_id = app_id_for(project_path)
    waivers = list_exceptions(project_path, app_id=app_id, status=status or None)
    if not waivers:
        return f"No exceptions recorded for {app_id}" + (f" with status '{status}'." if status else ".")
    return "\n".join(_format_waiver(w) for w in waivers)


@beta_tool
def revoke_project_exception(project_path: str, waiver_id: str, reason: str) -> str:
    """Revoke a previously recorded exception before its expiry.

    Args:
        project_path: Path to the project.
        waiver_id: The exception's id, from record_exception or list_project_exceptions.
        reason: Why it's being revoked (e.g. "risk materialized", "no longer applicable").
    """
    try:
        waiver = revoke_exception(project_path, waiver_id, reason)
    except KeyError as exc:
        return str(exc)
    return f"Revoked exception {waiver.waiver_id}: {reason}"


@beta_tool
def check_expiring_exceptions(project_path: str, within_days: int = 7) -> str:
    """List active exceptions expiring within the given number of days — the reminder half of exceptions tracking.

    Args:
        project_path: Path to the project.
        within_days: How many days ahead to check.
    """
    app_id = app_id_for(project_path)
    waivers = expiring_within(project_path, days=within_days, app_id=app_id)
    if not waivers:
        return f"No active exceptions for {app_id} expiring within {within_days} day(s)."
    return "\n".join(_format_waiver(w) for w in waivers)


EXCEPTIONS_TRACKING_TOOLS = [
    record_exception,
    list_project_exceptions,
    revoke_project_exception,
    check_expiring_exceptions,
]
