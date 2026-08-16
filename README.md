

# DevSecOps Assistant

This is a modular **DevSecOps Assistant** implemented in Python.

It is organized into:
- A reusable Python package: `core`
- A CLI entrypoint: `devsecops-assistant` (via `python -m core.cli`) for scripting
- A **chat entrypoint** (`python -m core.cli chat`) backed by a coordinator
  agent that delegates to specialist agents — the primary way this project
  is meant to grow (see `ROADMAP.md`)
- Modules:
  - **CI Onboarding** — auto-detect project & generate CI/CD pipelines for any CI tool
  - **Containerization** — auto-detect project & generate a Dockerfile, .dockerignore, optional docker-compose.yml, Kubernetes manifests, or a Helm chart
  - **Automation Frameworks** — auto-detect project & generate a Makefile, Dependabot config, and pre-commit config
  - **Security Scanning** — scan for hardcoded secrets, risky code patterns, and vulnerable dependencies; write a Markdown remediation report
  - **Registry** — the shared catalog specialists read/write to link their work together
  - **Template Engine** — render infra / Akamai / pipeline templates
  - **Akamai DevOps Engine** — thin wrapper around Akamai APIs
  - **Tools** — utilities such as Excel column comparison

> NOTE: This is a starter implementation. You can extend the modules with
> your own organization-specific logic, secrets management, and workflows.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Show CLI help
python -m core.cli -h
```

## Running tests

```bash
pip install -r requirements-dev.txt

pytest              # fast, free, deterministic — mocks the Claude API boundary
pytest -m live -v   # opt-in: hits the real API, needs ANTHROPIC_API_KEY, costs tokens
```

The default `pytest` run never makes a network call — `test_coordinator.py`
and the `test_*_specialist.py` files mock the Tool Runner boundary to
verify the assistant's own orchestration logic (message history, error
handling, delegation) without needing credentials. `test_live_chat.py` and
one test in `test_dependency_scan.py` are excluded by default (see
`pytest.ini`) and only run real end-to-end checks — against the live
model, and against a real `npm audit`, respectively — when you explicitly
ask for them.

## Chat with the coordinator

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login

python -m core.cli chat
```

The coordinator is a Claude Opus agent that delegates to specialist agents
rather than doing domain work itself — CI Onboarding, Containerization,
Automation Frameworks, and Security Scanning are on its roster so far.
Describe what you need in plain language ("onboard this project to GitHub
Actions", "containerize this app with a compose file", "generate a Helm
chart for this service", "set up pre-commit hooks for this repo", "scan
this project for hardcoded secrets") and it will ask for anything
load-bearing it's missing before delegating and acting.

## Example usage

### 1. Onboard a project to CI/CD (auto-detects language & tooling)

```bash
# Onboard current directory to GitHub Actions
python -m core.cli onboard --ci github-actions

# Onboard a specific project to GitLab CI
python -m core.cli onboard --project ./my-app --ci gitlab

# Preview without writing files (dry-run)
python -m core.cli onboard --ci jenkins --dry-run

# Override deploy branch
python -m core.cli onboard --ci azure --deploy-branch develop
```

**Supported CI tools:** `github-actions`, `gitlab`, `jenkins`, `azure`, `bitbucket`, `circleci`, `harness`

**Auto-detected languages:** Python, JavaScript/TypeScript, Java/Kotlin, Go, Rust, C#/.NET, Ruby

The assistant needs only **one required input** (`--ci`) — everything else (language, framework, build/test/lint commands, Docker usage) is auto-detected from your project files.

### 2. Containerize a project (Dockerfile + .dockerignore, optional compose)

```bash
# Generate a Dockerfile for the current directory
python -m core.cli containerize

# Preview without writing files (dry-run)
python -m core.cli containerize --dry-run

# Also generate a docker-compose.yml, and override the exposed port
python -m core.cli containerize --project ./my-app --compose --port 9000
```

Uses the same project detection as `onboard` and needs **zero required
inputs** — language, base image, install/build commands, run command, and
port are all inferred, with multi-stage builds for compiled languages
(Java, Kotlin, Go, Rust, C#) so the final image doesn't ship build tooling.

### 3. Generate Kubernetes manifests or a Helm chart

```bash
# Plain Deployment + Service manifests
python -m core.cli k8s

# A minimal, installable Helm chart instead
python -m core.cli k8s --helm

# Override replica count, port, and (manifests only) the image reference
python -m core.cli k8s --replicas 3 --port 9000 --image ghcr.io/org/app:v1

# Preview without writing files (dry-run)
python -m core.cli k8s --dry-run
```

Reuses the same project detection as `containerize` (service name from the
project directory, port from the detected framework). The image reference
defaults to `<service-name>:latest` — a placeholder matching what
`containerize`'s own suggested `docker build -t` command would produce —
since there's no way to infer a real registry path; override it with
`--image` (plain manifests) or by editing `values.yaml` after the fact
(Helm).

### 4. Scaffold dev-workflow automation (Makefile, Dependabot, pre-commit)

```bash
# Generate all three for the current directory
python -m core.cli automate

# Only the Makefile
python -m core.cli automate --targets makefile

# Preview without writing files (dry-run)
python -m core.cli automate --dry-run
```

Generates a `Makefile` (install/build/test/lint/clean, using the same
per-language command defaults as `onboard`), a `.github/dependabot.yml`
(covering the detected dependency ecosystem, plus `docker` and
`github-actions` if those are already present), and a
`.pre-commit-config.yaml` (baseline hygiene hooks always included, plus
local lint/test hooks when detected). Dependabot is skipped — not an
error — if nothing recognizable to point it at exists.

### 5. Scan for secrets, risky patterns, and vulnerable dependencies

```bash
# Full scan, print a summary (nothing written)
python -m core.cli security-scan --dry-run

# Full scan and write SECURITY_FINDINGS.md
python -m core.cli security-scan

# Just the secret scanner
python -m core.cli security-scan --no-patterns --no-dependencies
```

Three independent scanners, all read-only:
- **Secrets** — regex patterns for AWS/GitHub/Slack/Google/Stripe keys and
  PEM private keys (no external tools, no network calls); matched values
  are always redacted before they appear anywhere in output.
- **Risky patterns** — a lightweight, text-based check for known-dangerous
  idioms (`eval`/`exec`, `shell=True`, disabled TLS verification, unsafe
  deserialization) in Python and JS/TS. This is regex matching, not
  semantic analysis — it can flag comments, docstrings, or test fixtures
  alongside real code, so treat findings as a starting point for review,
  not a verdict.
- **Dependencies** — shells out to the ecosystem-standard scanner (`npm
  audit`, `pip-audit`, `cargo audit`, `govulncheck`) if it's installed;
  reports which tool is missing and how to install it if not.

Findings never turn into an auto-opened pull request or a source edit —
the report is the deliverable; applying fixes is a human decision.

### 6. Render a template

```bash
python -m core.cli template   --template examples/templates/akamai_property.json.j2   --values examples/values/akamai_property_values.yaml   --output out/property.json
```

### 7. Compare two Excel / CSV files

```bash
python -m core.cli excel-compare   --left examples/excel/left.csv   --right examples/excel/right.csv   --column key   --output out/diff.csv
```

### 8. Akamai: list properties (placeholder example)

```bash
python -m core.cli akamai list-properties   --config config/akamai.yaml
```

You can now push this project to:

- `https://github.com/narin-kura/devsecops-Assistant`

