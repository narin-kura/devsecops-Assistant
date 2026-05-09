"""Main onboarding orchestrator and CLI handler."""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Type

import yaml

from .providers.base import BaseProvider, OnboardingResult
from .providers.jenkins import JenkinsProvider
from .providers.github import GitHubProvider
from .providers.harness import HarnessProvider
from .providers.generic import GenericProvider

log = logging.getLogger(__name__)

_BUILT_IN_PROVIDERS: Dict[str, Type[BaseProvider]] = {
    "jenkins": JenkinsProvider,
    "github": GitHubProvider,
    "harness": HarnessProvider,
}

SUPPORTED_TOOLS = list(_BUILT_IN_PROVIDERS.keys()) + ["<any custom tool via generic provider>"]


def _load_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Onboarding config not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def run_onboarding(
    config_path: str,
    output_dir: str,
    tools: List[str] | None = None,
    dry_run: bool = False,
) -> int:
    """
    Orchestrate onboarding for all enabled tools in the config.

    Returns 0 on full success, 1 if any provider reported errors.
    """
    cfg = _load_config(config_path)
    project = cfg.get("project", {})

    if not project.get("name"):
        log.error("Config must include 'project.name'")
        return 1

    onboard_cfg: Dict[str, Any] = cfg.get("onboard_to", {})
    if not onboard_cfg:
        log.error("Config must include 'onboard_to' with at least one tool")
        return 1

    results: List[OnboardingResult] = []

    for tool_key, tool_cfg in onboard_cfg.items():
        if not isinstance(tool_cfg, dict):
            tool_cfg = {}

        if not tool_cfg.get("enabled", True):
            log.info("Skipping '%s' (disabled)", tool_key)
            continue

        if tools and tool_key not in tools:
            log.info("Skipping '%s' (not in --tools filter)", tool_key)
            continue

        log.info("Onboarding to: %s", tool_key)

        if tool_key in _BUILT_IN_PROVIDERS:
            provider: BaseProvider = _BUILT_IN_PROVIDERS[tool_key](project, tool_cfg)
        else:
            # Unknown tool key → treat as generic provider; the config must supply 'template'
            provider = GenericProvider(project, {"name": tool_key, **tool_cfg})

        result = provider.onboard()
        results.append(result)

        _print_result(result)

        if result.success and not dry_run:
            result.write_to_disk(output_dir)
            log.info("[%s] Files written to %s/%s/", tool_key, output_dir, tool_key)

    if not results:
        log.warning("No tools were processed. Check 'onboard_to' in your config.")
        return 1

    any_errors = any(not r.success for r in results)
    return 1 if any_errors else 0


def _print_result(result: OnboardingResult) -> None:
    status = "OK" if result.success else "FAILED"
    log.info("--- [%s] %s ---", result.tool, status)
    for msg in result.messages:
        for line in msg.splitlines():
            log.info("  %s", line)
    for err in result.errors:
        log.error("  ERROR: %s", err)
    if result.success:
        log.info("  Generated files:")
        for path in result.files:
            log.info("    - %s", path)


# --------------------------------------------------------------------------- #
# CLI handler (wired in cli.py)
# --------------------------------------------------------------------------- #
def onboard_cli(args) -> int:
    tools = [t.strip() for t in args.tools.split(",")] if getattr(args, "tools", None) else None
    return run_onboarding(
        config_path=args.config,
        output_dir=args.output_dir,
        tools=tools,
        dry_run=getattr(args, "dry_run", False),
    )
