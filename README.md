

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
handling, delegation) without needing credentials. `test_live_chat.py` is
excluded by default (see `pytest.ini`) and only runs real end-to-end checks
against the live model when you explicitly ask for it.

## Chat with the coordinator

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # or: ant auth login

python -m core.cli chat
```

The coordinator is a Claude Opus agent that delegates to specialist agents
rather than doing domain work itself — CI Onboarding, Containerization, and
Automation Frameworks are on its roster so far. Describe what you need in
plain language ("onboard this project to GitHub Actions", "containerize
this app with a compose file", "generate a Helm chart for this service",
"set up pre-commit hooks for this repo") and it will ask for anything
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

### 5. Render a template

```bash
python -m core.cli template   --template examples/templates/akamai_property.json.j2   --values examples/values/akamai_property_values.yaml   --output out/property.json
```

### 6. Compare two Excel / CSV files

```bash
python -m core.cli excel-compare   --left examples/excel/left.csv   --right examples/excel/right.csv   --column key   --output out/diff.csv
```

### 7. Akamai: list properties (placeholder example)

```bash
python -m core.cli akamai list-properties   --config config/akamai.yaml
```

You can now push this project to:

- `https://github.com/narin-kura/devsecops-Assistant`

