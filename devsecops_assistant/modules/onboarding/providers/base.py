"""Abstract base class for all onboarding providers."""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class OnboardingResult:
    """Holds the files and messages produced by a provider."""

    def __init__(self, tool: str):
        self.tool = tool
        self.files: Dict[str, str] = {}   # relative path -> content
        self.messages: List[str] = []
        self.errors: List[str] = []

    def add_file(self, rel_path: str, content: str) -> None:
        self.files[rel_path] = content

    def add_message(self, msg: str) -> None:
        self.messages.append(msg)

    def add_error(self, err: str) -> None:
        log.error("[%s] %s", self.tool, err)
        self.errors.append(err)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def write_to_disk(self, output_dir: str) -> None:
        """Write all generated files under *output_dir*."""
        for rel_path, content in self.files.items():
            full_path = os.path.join(output_dir, self.tool, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            log.info("  wrote %s", full_path)


class BaseProvider(ABC):
    """All onboarding providers must inherit from this class."""

    name: str = ""

    def __init__(self, project: Dict[str, Any], tool_cfg: Dict[str, Any]):
        self.project = project
        self.tool_cfg = tool_cfg

    @abstractmethod
    def onboard(self) -> OnboardingResult:
        """Generate all artefacts needed to onboard the project."""
