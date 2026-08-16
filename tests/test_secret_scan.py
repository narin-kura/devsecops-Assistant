"""Tests for the self-contained secret scanner.

Two of these are direct regressions for real bugs found while dogfooding
this module: a capture-group mismatch was redacting the wrong (tiny)
substring for rules with incidental parentheses, and the placeholder
denylist was checking the credential's *key name* instead of its *value*,
so `password = "changeme"` wasn't actually being filtered.
"""

from core.modules.security_scan.secret_scan import scan_secrets


def _write(tmp_path, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")


def test_detects_aws_access_key_id(tmp_path):
    _write(tmp_path, "config.py", 'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')

    findings = scan_secrets(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "aws-access-key-id"
    assert findings[0].severity == "critical"
    # Regression: value_group used to resolve to the (AKIA|ASIA) capture
    # group ("AKIA", 4 chars) instead of the full 20-char match.
    assert findings[0].snippet == "AKIA************MNOP"


def test_detects_github_token(tmp_path):
    _write(tmp_path, "config.py", f'GITHUB_TOKEN = "ghp_{"a" * 36}"\n')

    findings = scan_secrets(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "github-token"
    assert findings[0].severity == "critical"


def test_detects_private_key_header(tmp_path):
    _write(tmp_path, "id_rsa", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----\n")

    findings = scan_secrets(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "private-key-header"
    assert findings[0].line == 1


def test_generic_credential_denylist_filters_placeholders(tmp_path):
    # Regression: the denylist used to check the *key name* ("password"),
    # which is never itself a placeholder, so nothing was ever filtered.
    _write(
        tmp_path,
        "config.py",
        'password = "changeme"\n'
        'password = "reallysecretvalue123"\n'
        'token = "your_token_here"\n',
    )

    findings = scan_secrets(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].line == 2
    assert findings[0].rule_id == "generic-credential-assignment"
    assert findings[0].severity == "low"


def test_no_false_positive_on_clean_file(tmp_path):
    _write(tmp_path, "app.py", "def add(a, b):\n    return a + b\n")

    assert scan_secrets(str(tmp_path)) == []


def test_redaction_never_exposes_full_secret(tmp_path):
    _write(tmp_path, "config.py", f'GITHUB_TOKEN = "ghp_{"a" * 36}"\n')

    findings = scan_secrets(str(tmp_path))

    assert "a" * 36 not in findings[0].snippet
    assert "*" in findings[0].snippet


def test_skips_vendored_and_binary_paths(tmp_path):
    vendored = tmp_path / "node_modules" / "pkg"
    vendored.mkdir(parents=True)
    _write(vendored, "index.js", 'const key = "AKIAABCDEFGHIJKLMNOP";\n')

    assert scan_secrets(str(tmp_path)) == []


def test_finding_has_stable_id_across_identical_scans(tmp_path):
    _write(tmp_path, "config.py", 'AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')

    first = scan_secrets(str(tmp_path))
    second = scan_secrets(str(tmp_path))

    assert first[0].finding_id == second[0].finding_id
