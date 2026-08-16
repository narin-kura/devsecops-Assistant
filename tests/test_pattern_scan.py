"""Tests for the self-contained risky-pattern (SAST-lite) scanner."""

from core.modules.security_scan.pattern_scan import scan_patterns


def _write(tmp_path, name, content):
    dest = tmp_path / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")


def test_detects_python_eval(tmp_path):
    _write(tmp_path, "app.py", "result = eval(user_input)\n")

    findings = scan_patterns(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "py-eval"
    assert findings[0].severity == "high"
    assert findings[0].line == 1


def test_detects_python_subprocess_shell_true(tmp_path):
    _write(tmp_path, "app.py", "subprocess.run(cmd, shell=True)\n")

    findings = scan_patterns(str(tmp_path))

    assert any(f.rule_id == "py-subprocess-shell-true" for f in findings)


def test_detects_python_yaml_unsafe_load_but_not_safe_load(tmp_path):
    _write(tmp_path, "app.py", "data = yaml.load(stream)\nother = yaml.safe_load(stream)\n")

    findings = scan_patterns(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "py-yaml-unsafe-load"
    assert findings[0].line == 1


def test_yaml_load_with_explicit_loader_is_not_flagged(tmp_path):
    _write(tmp_path, "app.py", "data = yaml.load(stream, Loader=yaml.SafeLoader)\n")

    findings = scan_patterns(str(tmp_path))

    assert findings == []


def test_detects_js_eval_and_dangerous_dom_sink(tmp_path):
    _write(tmp_path, "app.js", "eval(userInput);\nel.innerHTML = userInput;\n")

    findings = scan_patterns(str(tmp_path))

    rule_ids = {f.rule_id for f in findings}
    assert "js-eval" in rule_ids
    assert "js-inner-html" in rule_ids


def test_dispatches_by_file_extension_not_project_language(tmp_path):
    # A JS-project repo can still have a stray Python build script -- rules
    # are chosen per file, not per the project's single detected language.
    _write(tmp_path, "package.json", '{"name": "demo"}')
    _write(tmp_path, "scripts/build.py", "eval(config)\n")

    findings = scan_patterns(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].rule_id == "py-eval"


def test_unrecognized_extension_is_not_scanned(tmp_path):
    _write(tmp_path, "notes.txt", "eval(something) shell=True\n")

    assert scan_patterns(str(tmp_path)) == []


def test_no_false_positive_on_clean_file(tmp_path):
    _write(tmp_path, "app.py", "def add(a, b):\n    return a + b\n")

    assert scan_patterns(str(tmp_path)) == []
