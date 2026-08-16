"""Agent-tool wrappers around the security-scanning module.

These are the tools the Security Scanning specialist calls. Every scan is
read-only against the target project (regex over local files, plus a
fixed-argv, non-shell invocation of an ecosystem-standard scanner binary) —
per ROADMAP.md's safety model, read/scan/report actions can run without a
confirm gate, unlike the mutate-class actions later phases will add.
"""

from __future__ import annotations

from anthropic import beta_tool

from ..ci_onboard.detector import detect
from ..registry.store import app_id_for, link, register_app
from .dependency_scan import scan_dependencies
from .pattern_scan import scan_patterns
from .remediation import format_report, run_full_scan, write_report
from .secret_scan import scan_secrets


@beta_tool
def scan_for_secrets(project_path: str) -> str:
    """Scan a project's source files for hardcoded credentials (AWS/GitHub/Slack/Google/Stripe keys, private key material, generic password/token assignments).

    Args:
        project_path: Path to the project to scan.
    """
    findings = scan_secrets(project_path)
    if not findings:
        return "No secrets detected."
    lines = [f"{len(findings)} potential secret(s) found:"]
    for f in findings:
        lines.append(f"  [{f.severity}] {f.rule_id} @ {f.file}:{f.line} — {f.snippet}")
    return "\n".join(lines)


@beta_tool
def scan_for_risky_patterns(project_path: str) -> str:
    """Scan a project's Python/JS/TS source for well-known risky code patterns (eval/exec, shell=True, disabled TLS verification, unsafe deserialization). Text-based matching, not semantic analysis — comments and strings can also match.

    Args:
        project_path: Path to the project to scan.
    """
    findings = scan_patterns(project_path)
    if not findings:
        return "No risky patterns detected."
    lines = [f"{len(findings)} risky pattern(s) found:"]
    for f in findings:
        lines.append(f"  [{f.severity}] {f.rule_id} @ {f.file}:{f.line}")
    return "\n".join(lines)


@beta_tool
def scan_for_vulnerable_dependencies(project_path: str) -> str:
    """Detect the project's dependency ecosystem and run its standard vulnerability scanner (npm audit, pip-audit, cargo audit, or govulncheck) if installed.

    Args:
        project_path: Path to the project to scan.
    """
    outcome = scan_dependencies(project_path)
    if not outcome.ran:
        return f"Dependency scan did not run: {outcome.note}"
    if not outcome.findings:
        return f"{outcome.tool_used} ran cleanly — no known vulnerabilities reported."
    lines = [f"{outcome.tool_used} found {len(outcome.findings)} issue(s):"]
    for f in outcome.findings:
        lines.append(f"  [{f.severity}] {f.message}")
    return "\n".join(lines)


@beta_tool
def run_security_scan(
    project_path: str,
    include_secrets: bool = True,
    include_patterns: bool = True,
    include_dependencies: bool = True,
    write_findings_report: bool = False,
) -> str:
    """Run the requested scanners together and optionally write a consolidated SECURITY_FINDINGS.md remediation report.

    Args:
        project_path: Path to the project to scan.
        include_secrets: Whether to run the secret scanner.
        include_patterns: Whether to run the risky-pattern scanner.
        include_dependencies: Whether to run the dependency vulnerability scanner.
        write_findings_report: If true, write SECURITY_FINDINGS.md to the project. If false, only preview counts — this defaults to False (not dry_run=True) because a scan is read-only regardless; only the report *file* is a write, so it needs its own explicit opt-in.
    """
    result = run_full_scan(
        project_path,
        include_secrets=include_secrets,
        include_patterns=include_patterns,
        include_dependencies=include_dependencies,
    )
    result.dry_run = not write_findings_report

    app_id = app_id_for(project_path)
    project = detect(project_path)
    register_app(project_path, app_id, language=project.language, framework=project.framework)

    if write_findings_report:
        write_report(result)
        link(
            project_path,
            app_id,
            "security",
            {
                "counts": result.counts_by_severity(),
                "report_path": str(result.report_path),
                "finding_ids": [f.finding_id for f in result.findings],
            },
        )

    return format_report(result)


SECURITY_SCAN_TOOLS = [
    scan_for_secrets,
    scan_for_risky_patterns,
    scan_for_vulnerable_dependencies,
    run_security_scan,
]
