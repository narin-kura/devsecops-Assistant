"""Self-contained risky-code-pattern scanning — a lightweight SAST, not a replacement for one.

Deliberately not called "SAST" in user-facing output: this is regex-based
detection of well-known dangerous idioms (eval/exec, shell=True, disabled
TLS verification, unsafe deserialization), not data-flow or taint
analysis. It catches real, common mistakes with zero external
dependencies; it does not replace a tool like Semgrep or Bandit for
anything requiring actual code analysis.

Rules are dispatched by file extension, not by the project's single
detected "primary" language — a JS project's stray Python build script
still gets scanned with the Python ruleset.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, NamedTuple

from .file_walk import iter_source_files
from .findings import Finding


class PatternRule(NamedTuple):
    rule_id: str
    pattern: "re.Pattern[str]"
    severity: str
    message: str


PYTHON_RULES: List[PatternRule] = [
    PatternRule(
        "py-eval",
        re.compile(r"\beval\s*\("),
        "high",
        "eval() on untrusted input allows arbitrary code execution. Use ast.literal_eval() for data, or a proper parser.",
    ),
    PatternRule(
        "py-exec",
        re.compile(r"\bexec\s*\("),
        "high",
        "exec() is a common injection vector. Avoid dynamic code execution on any input that isn't fully trusted.",
    ),
    PatternRule(
        "py-pickle-load",
        re.compile(r"\bpickle\.loads?\s*\("),
        "high",
        "Unpickling untrusted data allows arbitrary code execution. Use JSON or another safe serialization format.",
    ),
    PatternRule(
        "py-subprocess-shell-true",
        re.compile(r"\bsubprocess\.\w+\([^)]*shell\s*=\s*True"),
        "high",
        "shell=True enables shell injection if any argument includes untrusted input. Pass args as a list instead.",
    ),
    PatternRule(
        "py-yaml-unsafe-load",
        re.compile(r"\byaml\.load\s*\((?!.*Loader\s*=)"),
        "medium",
        "yaml.load() without an explicit safe Loader can execute arbitrary code. Use yaml.safe_load() instead.",
    ),
    PatternRule(
        "py-tls-verify-disabled",
        re.compile(r"\bverify\s*=\s*False\b"),
        "medium",
        "Disabling TLS certificate verification exposes the app to man-in-the-middle attacks.",
    ),
    PatternRule(
        "py-debug-true",
        re.compile(r"\bDEBUG\s*=\s*True\b"),
        "medium",
        "Debug mode should never be enabled in production — it can leak stack traces, source, and secrets.",
    ),
]

JS_RULES: List[PatternRule] = [
    PatternRule(
        "js-eval",
        re.compile(r"\beval\s*\("),
        "high",
        "eval() on untrusted input allows arbitrary code execution. Avoid dynamic evaluation entirely.",
    ),
    PatternRule(
        "js-new-function",
        re.compile(r"\bnew\s+Function\s*\("),
        "high",
        "The Function() constructor executes arbitrary code, similar in risk to eval().",
    ),
    PatternRule(
        "js-child-process-exec",
        re.compile(r"\bchild_process\.(exec|execSync)\s*\("),
        "high",
        "exec()/execSync() with unsanitized input risks shell injection. Prefer execFile()/spawn() with an argument array.",
    ),
    PatternRule(
        "js-inner-html",
        re.compile(r"\.innerHTML\s*="),
        "medium",
        "Assigning untrusted content to innerHTML risks XSS. Use textContent or a sanitizer.",
    ),
    PatternRule(
        "js-dangerously-set-inner-html",
        re.compile(r"\bdangerouslySetInnerHTML\b"),
        "medium",
        "dangerouslySetInnerHTML bypasses React's XSS protection. Ensure the content is sanitized first.",
    ),
    PatternRule(
        "js-tls-verify-disabled",
        re.compile(r"\brejectUnauthorized\s*:\s*false\b"),
        "medium",
        "Disabling TLS certificate verification exposes the app to man-in-the-middle attacks.",
    ),
]

_RULES_BY_EXTENSION: Dict[str, List[PatternRule]] = {
    ".py": PYTHON_RULES,
    ".js": JS_RULES,
    ".jsx": JS_RULES,
    ".ts": JS_RULES,
    ".tsx": JS_RULES,
}


def scan_patterns(project_path: str) -> List[Finding]:
    """Walk the project and flag lines matching a known-risky code pattern for that file's language."""
    findings: List[Finding] = []
    root = Path(project_path).resolve()

    for path in iter_source_files(project_path, extensions=set(_RULES_BY_EXTENSION)):
        rules = _RULES_BY_EXTENSION[path.suffix.lower()]
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        rel_path = str(path.relative_to(root))

        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in rules:
                match = rule.pattern.search(line)
                if not match:
                    continue
                findings.append(
                    Finding(
                        category="pattern",
                        severity=rule.severity,
                        rule_id=rule.rule_id,
                        message=rule.message,
                        file=rel_path,
                        line=line_no,
                        snippet=line.strip()[:120],
                    )
                )

    return findings
