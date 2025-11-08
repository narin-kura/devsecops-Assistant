import json
from pathlib import Path
from typing import Any, Dict

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _load_values(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Values file not found: {path}")
    if p.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported values file extension: {p.suffix}")


def render_template_file(template_path: str, values_path: str) -> str:
    template_path_obj = Path(template_path).resolve()
    env = Environment(
        loader=FileSystemLoader(str(template_path_obj.parent)),
        undefined=StrictUndefined,
        autoescape=False,
    )
    template = env.get_template(template_path_obj.name)
    values = _load_values(values_path)
    return template.render(**values)


def render_template_cli(args) -> int:
    output = render_template_file(args.template, args.values)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output, encoding="utf-8")
    print(f"[template] Rendered {args.template} -> {args.output}")
    return 0
