<<<<<<< HEAD
# devsecops-Assistant
=======
# DevSecOps Assistant

This is a modular **DevSecOps Assistant** skeleton implemented in Python.

It is organized into:
- A reusable Python package: `devsecops_assistant`
- A CLI entrypoint: `devsecops-assistant` (via `python -m devsecops_assistant.cli`)
- Modules:
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
python -m devsecops_assistant.cli -h
```

## Example usage

### 1. Render a template

```bash
python -m devsecops_assistant.cli template   --template examples/templates/akamai_property.json.j2   --values examples/values/akamai_property_values.yaml   --output out/property.json
```

### 2. Compare two Excel / CSV files

```bash
python -m devsecops_assistant.cli excel-compare   --left examples/excel/left.csv   --right examples/excel/right.csv   --column key   --output out/diff.csv
```

### 3. Akamai: list properties (placeholder example)

```bash
python -m devsecops_assistant.cli akamai list-properties   --config config/akamai.yaml
```

You can now push this project to:

- `https://github.com/narin-kura/devsecops-Assistant`
>>>>>>> b02cabc (chore: push all DevSecOps Assistant modules and updates)
