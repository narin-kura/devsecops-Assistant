"""Shared finding type for every scanner in this module (secret/pattern/dependency).

One uniform shape keeps aggregation/reporting/registry-linking code generic
across scan types, and gives every finding a stable `finding_id` — a short
hash of (category, rule_id, file, line) — so a future Exceptions Tracking
specialist can reference "the specific finding it waives" (per ROADMAP.md's
registry design) without needing today's scanners to change.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

SEVERITIES = ("critical", "high", "medium", "low", "info", "unknown")
_SEVERITY_ORDER = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class Finding:
    category: str  # "secret" | "pattern" | "dependency"
    severity: str  # one of SEVERITIES
    rule_id: str
    message: str
    file: str = ""
    line: Optional[int] = None
    snippet: str = ""
    finding_id: str = field(default="")

    def __post_init__(self) -> None:
        if self.severity not in _SEVERITY_ORDER:
            self.severity = "unknown"
        if not self.finding_id:
            basis = f"{self.category}:{self.rule_id}:{self.file}:{self.line}"
            self.finding_id = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]

    def sort_key(self):
        return (_SEVERITY_ORDER.get(self.severity, len(SEVERITIES)), self.file, self.line or 0)


def redact(value: str, keep: int = 4) -> str:
    """Show only the first/last *keep* characters of a matched secret.

    Findings and the reports built from them can end up committed, pasted
    into chat, or written to the registry — never reproduce the full secret
    value anywhere downstream of a match.
    """
    if len(value) <= keep * 2:
        return "*" * len(value)
    return f"{value[:keep]}{'*' * (len(value) - keep * 2)}{value[-keep:]}"
