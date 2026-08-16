"""Self-contained secret scanning — no external tools, no network calls.

Regex patterns for well-known credential formats (AWS, GitHub, Slack,
Google, Stripe, PEM private keys) are structurally fixed by their issuers,
so they're safe to hardcode with high confidence. The one generic
"password/token/secret = ..." pattern is a different story — it's the
noisiest possible rule by construction, so it's kept at "low" severity and
filtered against a placeholder denylist to cut obvious false positives
(examples, "changeme", empty templates) before it ever becomes a finding.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, NamedTuple

from .file_walk import iter_source_files
from .findings import Finding, redact


class SecretRule(NamedTuple):
    rule_id: str
    pattern: "re.Pattern[str]"
    severity: str
    message: str
    # Which capture group holds the actual secret value (for redaction and
    # denylist checks) — 0 means "the whole match". Must be explicit rather
    # than inferred: a rule's parentheses can just as easily be a
    # non-capturing alternation or an unrelated prefix group, and guessing
    # wrong silently redacts/denylists the wrong substring.
    value_group: int = 0


_PLACEHOLDER_DENYLIST = re.compile(
    r"^(changeme|change_me|xxx+|\*+|your[_-]?(key|token|secret|password)([_-]?here)?|"
    r"example|sample|test|dummy|placeholder|todo|fixme|<[^>]*>|\$\{[^}]*\})$",
    re.IGNORECASE,
)

SECRET_RULES: List[SecretRule] = [
    SecretRule(
        "aws-access-key-id",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        "critical",
        "AWS access key ID found. Rotate the credential immediately and remove it from source.",
    ),
    SecretRule(
        "aws-secret-access-key",
        re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"),
        "critical",
        "AWS secret access key found. Rotate the credential immediately and remove it from source.",
        value_group=1,
    ),
    SecretRule(
        "github-token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "critical",
        "GitHub token found. Revoke it in GitHub settings and remove it from source.",
    ),
    SecretRule(
        "github-fine-grained-pat",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        "critical",
        "GitHub fine-grained personal access token found. Revoke it and remove it from source.",
    ),
    SecretRule(
        "slack-token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "high",
        "Slack token found. Revoke it in Slack app settings and remove it from source.",
    ),
    SecretRule(
        "slack-webhook",
        re.compile(r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+"),
        "high",
        "Slack webhook URL found. Regenerate it and remove it from source.",
    ),
    SecretRule(
        "google-api-key",
        re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
        "high",
        "Google API key found. Restrict or rotate it in Google Cloud console and remove it from source.",
    ),
    SecretRule(
        "stripe-live-key",
        re.compile(r"\bsk_live_[0-9a-zA-Z]{24,}\b"),
        "critical",
        "Stripe live secret key found. Roll it immediately in the Stripe dashboard and remove it from source.",
    ),
    SecretRule(
        "private-key-header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
        "critical",
        "Private key material found in source. Remove it, rotate the corresponding key pair, and use a secrets manager.",
    ),
    SecretRule(
        "generic-credential-assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|pwd|token)\s*[:=]\s*['\"]([^'\"]{8,})['\"]"),
        "low",
        "Possible hardcoded credential. Verify this isn't a real secret, then move it to an environment variable or secrets manager.",
        value_group=1,
    ),
]


def scan_secrets(project_path: str) -> List[Finding]:
    """Walk the project's source files and flag anything matching a secret pattern."""
    findings: List[Finding] = []
    root = Path(project_path).resolve()

    for path in iter_source_files(project_path):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel_path = str(path.relative_to(root))

        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in SECRET_RULES:
                match = rule.pattern.search(line)
                if not match:
                    continue
                matched_value = match.group(rule.value_group)
                if rule.rule_id == "generic-credential-assignment" and _PLACEHOLDER_DENYLIST.match(matched_value):
                    continue
                findings.append(
                    Finding(
                        category="secret",
                        severity=rule.severity,
                        rule_id=rule.rule_id,
                        message=rule.message,
                        file=rel_path,
                        line=line_no,
                        snippet=redact(matched_value),
                    )
                )

    return findings
