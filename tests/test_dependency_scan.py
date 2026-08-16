"""Tests for the dependency vulnerability scanner.

Mocks shutil.which/subprocess.run for the deterministic, no-network suite.
`test_npm_audit_end_to_end_against_real_npm` is the one exception — it
actually shells out to a real `npm audit` (skipped if npm isn't on PATH),
grounding the npm parser against real tool output rather than only a
hand-written fixture. This is the same "mock the boundary for the main
suite, keep one opt-in real check" split test_live_chat.py established for
the Claude API boundary.
"""

import json
import shutil
import subprocess
import sys

import pytest

from core.modules.ci_onboard.detector import ProjectProfile
from core.modules.security_scan.dependency_scan import scan_dependencies

NPM_AUDIT_FIXTURE = json.dumps(
    {
        "auditReportVersion": 2,
        "vulnerabilities": {
            "lodash": {
                "name": "lodash",
                "severity": "critical",
                "isDirect": True,
                "via": [
                    {
                        "source": 1106913,
                        "name": "lodash",
                        "title": "Command Injection in lodash",
                        "url": "https://github.com/advisories/GHSA-35jh-r3h4-6jhm",
                        "severity": "high",
                    }
                ],
                "fixAvailable": {"name": "lodash", "version": "4.17.21", "isSemVerMajor": False},
            }
        },
        "metadata": {"vulnerabilities": {"critical": 1, "total": 1}},
    }
)


def test_unrecognized_ecosystem_does_not_run_anything(tmp_path):
    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="unknown"))

    assert outcome.ran is False
    assert outcome.tool_used is None


def test_missing_tool_reports_install_hint(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)

    outcome = scan_dependencies(
        str(tmp_path), project=ProjectProfile(language="python", package_manager="pip")
    )

    assert outcome.ran is False
    assert outcome.tool_used == "pip-audit"
    assert "pip install pip-audit" in outcome.note


def test_pip_without_requirements_txt_reports_unsupported(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pip-audit")

    outcome = scan_dependencies(
        str(tmp_path), project=ProjectProfile(language="python", package_manager="pip")
    )

    assert outcome.ran is False
    assert "doesn't have a manifest" in outcome.note


def test_npm_audit_parses_real_recorded_output(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "npm")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=1, stdout=NPM_AUDIT_FIXTURE, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="javascript", package_manager="npm"))

    assert outcome.ran is True
    assert len(outcome.findings) == 1
    finding = outcome.findings[0]
    assert finding.severity == "critical"
    assert "lodash" in finding.message
    assert "4.17.21" in finding.message


def test_clean_scan_produces_no_findings_and_a_note(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "npm")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout='{"vulnerabilities": {}}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="javascript", package_manager="npm"))

    assert outcome.ran is True
    assert outcome.findings == []
    assert "no known vulnerabilities" in outcome.note


def test_timeout_is_reported_not_raised(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "npm")

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, timeout=90)

    monkeypatch.setattr(subprocess, "run", fake_run)

    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="javascript", package_manager="npm"))

    assert outcome.ran is False
    assert "timed out" in outcome.note


def test_unparseable_generic_output_degrades_to_summary_finding(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: "cargo-audit")

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="not json at all, just text", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="rust", package_manager="cargo"))

    assert outcome.ran is True
    assert len(outcome.findings) == 1
    assert "couldn't confidently parse" in outcome.findings[0].message


def test_windows_wraps_shimmed_binaries_via_cmd(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    (tmp_path / "package.json").write_text('{"name": "demo"}', encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "npm")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, returncode=0, stdout='{"vulnerabilities": {}}', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    scan_dependencies(str(tmp_path), project=ProjectProfile(language="javascript", package_manager="npm"))

    assert captured["cmd"][:2] == ["cmd", "/c"]


@pytest.mark.live
@pytest.mark.skipif(shutil.which("npm") is None, reason="npm not on PATH")
def test_npm_audit_end_to_end_against_real_npm(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"name": "audit-probe", "version": "1.0.0", "dependencies": {"lodash": "4.17.11"}}',
        encoding="utf-8",
    )
    subprocess.run(
        ["cmd", "/c", "npm", "install", "--package-lock-only"] if sys.platform == "win32"
        else ["npm", "install", "--package-lock-only"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
    )

    outcome = scan_dependencies(str(tmp_path), project=ProjectProfile(language="javascript", package_manager="npm"))

    assert outcome.ran is True
    assert any(f.rule_id == "npm:lodash" for f in outcome.findings)
