"""Opt-in tests against the real Claude API.

These are deselected by default (see pytest.ini: `addopts = -m "not live"`)
and skipped unless ANTHROPIC_API_KEY is set, since they cost real tokens and
need network access. Run them deliberately once you have credentials:

    pytest -m live -v

If you authenticate via `ant auth login` instead of an API key, this file's
skip condition won't detect that — export ANTHROPIC_API_KEY as a fallback,
or comment out the skipif locally to force a run.
"""

import os

import pytest

from core.agents.specialists import ci_onboarding

pytestmark = pytest.mark.live

requires_credentials = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="requires a live ANTHROPIC_API_KEY — not set, skipping live test",
)


@requires_credentials
def test_ci_onboarding_specialist_completes_a_real_dry_run(tmp_path):
    (tmp_path / "requirements.txt").write_text("flask==3.0.0\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    report = ci_onboarding.run(
        f"Detect the project at {tmp_path} and preview (dry run only — do not write any "
        f"files) a github-actions pipeline for it. Report what language you detected and "
        f"what you would write."
    )

    assert "python" in report.lower()
    # A dry run must never touch disk, live model or not.
    assert not (tmp_path / ".github").exists()
