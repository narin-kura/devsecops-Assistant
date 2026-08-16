"""Dependency vulnerability scanning — shells out to the ecosystem-standard scanner.

Deliberately does NOT reinvent a vulnerability database: that data changes
constantly and is already maintained by each ecosystem's own tool (npm
audit, pip-audit, cargo audit, govulncheck). This module's job is
detection (is the tool installed?), safe invocation (fixed argv list, never
shell=True, a hard timeout), and parsing.

Parsing confidence is NOT uniform across tools, and says so honestly:
npm's `audit --json` schema was verified against real output from this
tool during development (see tests/test_dependency_scan.py's recorded
fixture). pip-audit / cargo-audit / govulncheck were not installed in the
development environment, so their parsers are best-effort against
documented shapes and fall back to a generic summary on any mismatch
rather than silently reporting wrong structured fields.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, NamedTuple, Optional

from ..ci_onboard.detector import ProjectProfile, detect
from .findings import Finding

_TIMEOUT_SECONDS = 90


class ScannerSpec(NamedTuple):
    tool_name: str  # binary checked via shutil.which()
    package_manager: str  # matches ProjectProfile.package_manager
    build_command: Callable[[Path], Optional[List[str]]]
    install_hint: str
    parser: str  # "npm" or "generic"


def _npm_cmd(root: Path) -> Optional[List[str]]:
    return ["npm", "audit", "--json"]


def _pip_audit_cmd(root: Path) -> Optional[List[str]]:
    if not (root / "requirements.txt").exists():
        return None
    return ["pip-audit", "-r", "requirements.txt", "--format", "json"]


def _cargo_audit_cmd(root: Path) -> Optional[List[str]]:
    return ["cargo", "audit", "--json"]


def _govulncheck_cmd(root: Path) -> Optional[List[str]]:
    return ["govulncheck", "-json", "./..."]


_SCANNERS = {
    "npm": ScannerSpec("npm", "npm", _npm_cmd, "npm ships with Node.js", "npm"),
    "pip": ScannerSpec("pip-audit", "pip", _pip_audit_cmd, "pip install pip-audit", "generic"),
    "cargo": ScannerSpec("cargo-audit", "cargo", _cargo_audit_cmd, "cargo install cargo-audit", "generic"),
    "go modules": ScannerSpec(
        "govulncheck", "go modules", _govulncheck_cmd,
        "go install golang.org/x/vuln/cmd/govulncheck@latest", "generic",
    ),
}


@dataclass
class DependencyScanOutcome:
    """What happened when trying to scan dependencies — always meaningful, never a crash."""

    ecosystem: Optional[str]
    tool_used: Optional[str]
    ran: bool
    findings: List[Finding] = field(default_factory=list)
    note: str = ""


def _parse_npm_audit(stdout: str) -> List[Finding]:
    findings: List[Finding] = []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return findings

    for pkg_name, vuln in (data.get("vulnerabilities") or {}).items():
        advisories = [v for v in (vuln.get("via") or []) if isinstance(v, dict)]
        titles = "; ".join(a.get("title", "") for a in advisories if a.get("title")) or f"{pkg_name} has a known vulnerability"
        urls = [a.get("url", "") for a in advisories if a.get("url")]

        fix = vuln.get("fixAvailable")
        if isinstance(fix, dict):
            fix_msg = f" Fix: upgrade to {fix.get('name')}@{fix.get('version')}."
        elif fix is True:
            fix_msg = " Fix: run `npm audit fix`."
        else:
            fix_msg = " No automatic fix available yet."

        findings.append(
            Finding(
                category="dependency",
                severity=vuln.get("severity", "unknown"),
                rule_id=f"npm:{pkg_name}",
                message=f"{pkg_name}: {titles}.{fix_msg}",
                file="package.json",
                snippet="; ".join(urls[:3]),
            )
        )
    return findings


def _parse_generic_best_effort(tool_name: str, stdout: str) -> List[Finding]:
    """Best-effort extraction for tools whose exact JSON shape wasn't verified live.

    Tries a handful of documented-but-unconfirmed field-name guesses; on any
    mismatch, degrades to one summary finding rather than fabricating
    structured detail that might not reflect what the tool actually said.
    """
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = None

    entries = []
    if isinstance(data, dict):
        entries = data.get("dependencies") or data.get("vulnerabilities", {}).get("list") or []
        if isinstance(entries, dict):
            entries = entries.get("dependencies", [])
    elif isinstance(data, list):
        entries = data

    findings: List[Finding] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        pkg = entry.get("name") or entry.get("package", {}).get("name") or "unknown package"

        vulns = entry.get("vulns")
        if not vulns and entry.get("advisory"):
            vulns = [entry["advisory"]]
        if isinstance(vulns, dict):
            vulns = [vulns]

        for v in vulns or []:
            if not isinstance(v, dict):
                continue
            aliases = v.get("aliases") or []
            vid = v.get("id") or (aliases[0] if aliases else "unknown")
            findings.append(
                Finding(
                    category="dependency",
                    severity=v.get("severity") or "unknown",
                    rule_id=f"{tool_name}:{vid}",
                    message=f"{pkg}: {v.get('title') or v.get('description') or vid}",
                )
            )

    if findings:
        return findings

    if stdout.strip():
        return [
            Finding(
                category="dependency",
                severity="unknown",
                rule_id=f"{tool_name}:unparsed",
                message=(
                    f"{tool_name} ran and produced output, but this build couldn't confidently parse its "
                    f"structure ({len(stdout)} bytes). Run `{tool_name}` directly for the full report."
                ),
            )
        ]
    return []


def scan_dependencies(project_path: str, project: Optional[ProjectProfile] = None) -> DependencyScanOutcome:
    """Detect the project's ecosystem and run its standard vulnerability scanner, if available."""
    project = project or detect(project_path)
    root = Path(project_path).resolve()
    spec = _SCANNERS.get(project.package_manager or "")

    if spec is None:
        return DependencyScanOutcome(
            ecosystem=project.package_manager,
            tool_used=None,
            ran=False,
            note=(
                f"No automated dependency scanner wired up yet for '{project.package_manager or project.language}'."
                if project.language != "unknown"
                else "Could not detect a dependency ecosystem to scan."
            ),
        )

    if shutil.which(spec.tool_name) is None:
        return DependencyScanOutcome(
            ecosystem=project.package_manager,
            tool_used=spec.tool_name,
            ran=False,
            note=f"{spec.tool_name} not found on PATH. Install with: {spec.install_hint}",
        )

    cmd = spec.build_command(root)
    if cmd is not None and sys.platform == "win32":
        # Console-script shims (npm.CMD and similar) can't be launched by
        # CreateProcess directly -- only cmd.exe knows how to run a .CMD/.BAT
        # file. Safe here specifically because every element of `cmd` is a
        # hardcoded constant (never interpolated user/project input), so
        # this isn't the shell-injection risk that shell=True would be.
        cmd = ["cmd", "/c"] + cmd
    if cmd is None:
        return DependencyScanOutcome(
            ecosystem=project.package_manager,
            tool_used=spec.tool_name,
            ran=False,
            note=f"{spec.tool_name} is available, but this project doesn't have a manifest it knows how to scan directly.",
        )

    try:
        result = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, timeout=_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return DependencyScanOutcome(
            ecosystem=project.package_manager,
            tool_used=spec.tool_name,
            ran=False,
            note=f"{spec.tool_name} timed out after {_TIMEOUT_SECONDS}s.",
        )
    except OSError as exc:
        return DependencyScanOutcome(
            ecosystem=project.package_manager,
            tool_used=spec.tool_name,
            ran=False,
            note=f"Failed to run {spec.tool_name}: {exc}",
        )

    stdout = result.stdout or ""
    if spec.parser == "npm":
        findings = _parse_npm_audit(stdout)
    else:
        findings = _parse_generic_best_effort(spec.tool_name, stdout)

    return DependencyScanOutcome(
        ecosystem=project.package_manager,
        tool_used=spec.tool_name,
        ran=True,
        findings=findings,
        note="" if findings else f"{spec.tool_name} ran cleanly — no known vulnerabilities reported.",
    )
