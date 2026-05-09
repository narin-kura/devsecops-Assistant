"""Generic / custom tool onboarding provider.

Uses Jinja2 templates supplied by the caller — enabling onboarding to any tool
(ArgoCD, GitLab, Terraform Cloud, PagerDuty, Datadog, etc.).

Config block expected under the tool key:
  template:  path/to/template.j2       # required
  output:    path/to/output_file       # optional, defaults to tool-name/output.txt
  values:    path/to/extra_values.yaml # optional extra values merged into context
"""
from __future__ import annotations

import os
from typing import Any, Dict

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .base import BaseProvider, OnboardingResult


def _load_extra_values(values_path: str) -> Dict[str, Any]:
    if not values_path:
        return {}
    if not os.path.exists(values_path):
        raise FileNotFoundError(f"values file not found: {values_path}")
    with open(values_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class GenericProvider(BaseProvider):
    """Render one or more Jinja2 templates for any tool."""

    name = "generic"

    def onboard(self) -> OnboardingResult:
        tool_name = self.tool_cfg.get("name", "custom-tool")
        result = OnboardingResult(tool_name)

        templates_cfg = self.tool_cfg.get("templates")
        if not templates_cfg:
            # Support single-template shorthand
            tpl = self.tool_cfg.get("template")
            if not tpl:
                result.add_error(
                    f"[{tool_name}] 'templates' (list) or 'template' (string) is required"
                )
                return result
            templates_cfg = [
                {
                    "template": tpl,
                    "output": self.tool_cfg.get("output", "output.txt"),
                    "values": self.tool_cfg.get("values", ""),
                }
            ]

        for entry in templates_cfg:
            tpl_path = entry.get("template", "")
            if not os.path.exists(tpl_path):
                result.add_error(f"Template not found: {tpl_path}")
                continue

            tpl_dir = os.path.dirname(os.path.abspath(tpl_path))
            tpl_file = os.path.basename(tpl_path)

            try:
                extra = _load_extra_values(entry.get("values", ""))
            except FileNotFoundError as exc:
                result.add_error(str(exc))
                continue

            ctx = {"project": self.project, **extra}

            env = Environment(
                loader=FileSystemLoader(tpl_dir),
                undefined=StrictUndefined,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            try:
                rendered = env.get_template(tpl_file).render(**ctx)
            except Exception as exc:  # noqa: BLE001
                result.add_error(f"Template render error ({tpl_path}): {exc}")
                continue

            out_rel = entry.get("output", tpl_file.removesuffix(".j2"))
            result.add_file(out_rel, rendered)

        if result.success:
            result.add_message(
                f"{tool_name} artefacts generated from custom templates.\n"
                f"  Review the output files under the '{tool_name}/' directory."
            )
        return result
