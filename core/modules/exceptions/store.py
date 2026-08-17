"""Exceptions Tracking store — a system of record for accepted security risks/waivers.

Unlike every specialist built so far (render a file, forget it), this one
needs genuine mutable state: a waiver is created, may later be revoked,
and its status (active/expired/revoked) has to be computed correctly as
time passes -- not just an append-only history the way the shared
registry's link() entries work. Lives in its own file,
`.devsecops/exceptions.json`, alongside registry.json in the same
per-project hidden directory.

The dataclass is named Waiver, not Exception -- shadowing the builtin
`Exception` inside this module would break any `except Exception:` clause
written later in the same file. User-facing function names still say
"exception" (create_exception, list_exceptions, ...) since those match
this project's terminology (ROADMAP.md's "Exceptions Tracking") and don't
collide with anything.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STORE_DIRNAME = ".devsecops"
STORE_FILENAME = "exceptions.json"


def _store_path(project_path: str) -> Path:
    return Path(project_path).resolve() / STORE_DIRNAME / STORE_FILENAME


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_expiry(value: str) -> datetime:
    """Parse an ISO date/datetime string, treating a bare date (no offset) as UTC.

    Python's datetime.fromisoformat() (3.8 here) happily parses a
    date-only string like "2026-12-01" into a *naive* datetime -- the most
    natural way to specify "when does this expire" -- but comparing that
    against datetime.now(timezone.utc) raises TypeError ("can't compare
    offset-naive and offset-aware datetimes"). Normalize once, here, so
    every caller gets a comparable, timezone-aware value.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _load(project_path: str) -> Dict[str, Any]:
    path = _store_path(project_path)
    if not path.exists():
        return {"waivers": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(project_path: str, data: Dict[str, Any]) -> None:
    path = _store_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


@dataclass
class Waiver:
    waiver_id: str
    app_id: str
    description: str
    justification: str
    approved_by: str
    created_at: str
    expires_at: str
    finding_id: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_reason: Optional[str] = None

    def status(self) -> str:
        if self.revoked_at:
            return "revoked"
        if _parse_expiry(self.expires_at) <= _now():
            return "expired"
        return "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_exception(
    project_path: str,
    app_id: str,
    description: str,
    justification: str,
    approved_by: str,
    expires_at: str,
    finding_id: Optional[str] = None,
) -> Waiver:
    """Record a new risk acceptance. *expires_at* is an ISO date/datetime string.

    Every waiver must have an expiry -- an exception with no review date is
    how accepted risks quietly become permanent. Parsed up front so a
    malformed date fails loudly here instead of surfacing later as a
    confusing error when computing status().
    """
    _parse_expiry(expires_at)

    waiver = Waiver(
        waiver_id=uuid.uuid4().hex[:12],
        app_id=app_id,
        description=description,
        justification=justification,
        approved_by=approved_by,
        created_at=_now().isoformat(),
        expires_at=expires_at,
        finding_id=finding_id,
    )

    data = _load(project_path)
    data.setdefault("waivers", []).append(waiver.to_dict())
    _save(project_path, data)
    return waiver


def list_exceptions(
    project_path: str,
    app_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Waiver]:
    data = _load(project_path)
    waivers = [Waiver(**w) for w in data.get("waivers", [])]
    if app_id:
        waivers = [w for w in waivers if w.app_id == app_id]
    if status:
        waivers = [w for w in waivers if w.status() == status]
    return waivers


def get_exception(project_path: str, waiver_id: str) -> Optional[Waiver]:
    for w in list_exceptions(project_path):
        if w.waiver_id == waiver_id:
            return w
    return None


def revoke_exception(project_path: str, waiver_id: str, reason: str) -> Waiver:
    data = _load(project_path)
    for entry in data.get("waivers", []):
        if entry["waiver_id"] == waiver_id:
            entry["revoked_at"] = _now().isoformat()
            entry["revoked_reason"] = reason
            _save(project_path, data)
            return Waiver(**entry)
    raise KeyError(f"No exception found with id '{waiver_id}'")


def expiring_within(project_path: str, days: int = 7, app_id: Optional[str] = None) -> List[Waiver]:
    """Active waivers whose expiry falls within the next *days* days -- the "reminders" half of item 4."""
    cutoff = _now() + timedelta(days=days)
    return [
        w for w in list_exceptions(project_path, app_id=app_id, status="active")
        if _parse_expiry(w.expires_at) <= cutoff
    ]


def find_waiver_for_finding(project_path: str, finding_id: str) -> Optional[Waiver]:
    """The concrete Security Scanning integration point: is this finding currently waived?"""
    for w in list_exceptions(project_path, status="active"):
        if w.finding_id == finding_id:
            return w
    return None
