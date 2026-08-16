

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
and `test_ci_onboarding_specialist.py` mock the Tool Runner boundary to
verify the assistant's own orchestration logic (message history, error
handling, delegation) without needing credentials. `test_live_chat.py` is
excluded by default (see `pytest.ini`) and only runs real end-to-end checks
against the live model when you explicitly ask for it.

## Chat with the coordinator

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login

python -m core.cli chat
```

The coordinator is a Claude Opus agent that delegates to specialist agents
rather than doing domain work itself — right now the CI Onboarding
specialist is on its roster. Describe what you need in plain language
("onboard this project to GitHub Actions") and it will ask for anything
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

### 2. Render a template

```bash
python -m core.cli template   --template examples/templates/akamai_property.json.j2   --values examples/values/akamai_property_values.yaml   --output out/property.json
```

### 3. Compare two Excel / CSV files

```bash
python -m core.cli excel-compare   --left examples/excel/left.csv   --right examples/excel/right.csv   --column key   --output out/diff.csv
```

### 4. Akamai: list properties (placeholder example)

```bash
python -m core.cli akamai list-properties   --config config/akamai.yaml
```

You can now push this project to:

- `https://github.com/narin-kura/devsecops-Assistant`

