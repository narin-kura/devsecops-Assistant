"""Aggregates secret/pattern/dependency scan output into one report.

"Remediation" here means a concrete, actionable Markdown report — file,
line, what's wrong, and a specific fix — not an auto-opened pull request.
Actually mutating a repo (branches, commits, PRs) is a materially bigger
scope (needs git plumbing and a GitHub token) and a different risk class
than everything else this specialist does, which is entirely read-only
scanning plus writing one report file. Scoped out deliberately, same as
K8s/Helm was split out of the first Containerization pass — see
ROADMAP.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .dependency_scan import DependencyScanOutcome
from .findings import SEVERITIES, Finding

DEFAULT_REPORT_FILENAME = "SECURITY_FINDINGS.md"


@dataclass
class SecurityScanResult:
    project_path: str
    findings: List[Finding] = field(default_factory=list)
    dependency_outcome: Optional[DependencyScanOutcome] = None
    dry_run: bool = False
    report_path: Optional[Path] = None

    def counts_by_severity(self) -> Dict[str, int]:
        counts = {s: 0 for s in SEVERITIES}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts


def run_full_scan(
    project_path: str,
    include_secrets: bool = True,
    include_patterns: bool = True,
    include_dependencies: bool = True,
) -> SecurityScanResult:
    """Run the requested scanners and return one aggregated, sorted result."""
    # Imported lazily to keep this module's own import graph flat and to
    # make it obvious each scanner is independently optional.
    from .dependency_scan import scan_dependencies
    from .pattern_scan import scan_patterns
    from .secret_scan import scan_secrets

    findings: List[Finding] = []
    dependency_outcome: Optional[DependencyScanOutcome] = None

    if include_secrets:
        findings.extend(scan_secrets(project_path))
    if include_patterns:
        findings.extend(scan_patterns(project_path))
    if include_dependencies:
        dependency_outcome = scan_dependencies(project_path)
        findings.extend(dependency_outcome.findings)

    findings.sort(key=lambda f: f.sort_key())

    return SecurityScanResult(
        project_path=project_path,
        findings=findings,
        dependency_outcome=dependency_outcome,
    )


def build_markdown_report(result: SecurityScanResult) -> str:
    counts = result.counts_by_severity()
    lines = [
        "# Security Findings",
        "",
        f"Scanned: `{result.project_path}`",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "|---|---|",
    ]
    for severity in SEVERITIES:
        if counts[severity]:
            lines.append(f"| {severity} | {counts[severity]} |")
    lines.append(f"| **total** | **{len(result.findings)}** |")
    lines.append("")

    if result.dependency_outcome and not result.dependency_outcome.ran:
        lines.append(f"> Dependency scan did not run: {result.dependency_outcome.note}")
        lines.append("")

    if not result.findings:
        lines.append("No findings.")
        lines.append("")
    else:
        lines.append("## Findings")
        lines.append("")
        for f in result.findings:
            location = f"{f.file}:{f.line}" if f.line else (f.file or "—")
            lines.append(f"### [{f.severity.upper()}] {f.rule_id} — `{location}`")
            lines.append("")
            lines.append(f.message)
            if f.snippet:
                lines.append("")
                lines.append(f"```\n{f.snippet}\n```")
            lines.append("")
            lines.append(f"*Finding ID: `{f.finding_id}`*")
            lines.append("")

    lines.append(
        "---\n"
        "Note: pattern-based findings are text matches, not semantic analysis — "
        "they can flag comments, docstrings, or test fixtures alongside real "
        "code. Review each finding before acting on it. This report does not "
        "open pull requests or modify source; apply fixes yourself."
    )

    return "\n".join(lines)


def format_report(result: SecurityScanResult) -> str:
    """Render a human-readable summary for CLI/chat presentation."""
    counts = result.counts_by_severity()
    lines = [
        "",
        "╔══════════════════════════════════════════════════════╗",
        "║   DevSecOps Assistant — Security Scan                ║",
        "╚══════════════════════════════════════════════════════╝",
        "",
        f"🔍 Scanned: {result.project_path}",
        "",
    ]
    for severity in SEVERITIES:
        if counts[severity]:
            lines.append(f"   {severity:<10}: {counts[severity]}")
    lines.append(f"   {'total':<10}: {len(result.findings)}")
    lines.append("")

    if result.dependency_outcome and not result.dependency_outcome.ran:
        lines.append(f"⚠️  Dependency scan skipped: {result.dependency_outcome.note}")
        lines.append("")

    if result.report_path:
        lines.append(f"✅ Full report written to: {result.report_path}")
    elif result.dry_run:
        lines.append("📄 Dry run — report not written. Findings:")
        for f in result.findings[:20]:
            location = f"{f.file}:{f.line}" if f.line else (f.file or "—")
            lines.append(f"   [{f.severity}] {f.rule_id} @ {location}")
        if len(result.findings) > 20:
            lines.append(f"   ... and {len(result.findings) - 20} more")

    return "\n".join(lines)


def write_report(result: SecurityScanResult, output_path: Optional[str] = None) -> SecurityScanResult:
    dest = Path(output_path) if output_path else Path(result.project_path).resolve() / DEFAULT_REPORT_FILENAME
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(build_markdown_report(result), encoding="utf-8")
    result.report_path = dest
    return result


def security_scan_cli(args) -> int:
    """CLI entry point for the security-scan subcommand."""
    from ...logging_utils import get_logger

    log = get_logger(__name__)
    try:
        result = run_full_scan(
            args.project,
            include_secrets=not args.no_secrets,
            include_patterns=not args.no_patterns,
            include_dependencies=not args.no_dependencies,
        )
        result.dry_run = args.dry_run
        if not args.dry_run:
            write_report(result, args.output)
        print(format_report(result))
        return 0
    except Exception as exc:
        log.error("Security scan failed: %s", exc)
        print(f"\n❌ Error: {exc}")
        return 1
