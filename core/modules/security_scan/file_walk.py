"""Shared source-file walker for the secret and pattern scanners.

Skips directories that are never hand-authored (VCS internals, dependency
caches, build output) using the same directory-name conventions already
established across this project's per-language defaults (see
ci_onboard/profiles.py's cache_paths and containerize/*.dockerignore.j2),
plus a file-size cutoff so a stray data dump doesn't get read into memory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional, Set

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    "vendor", "dist", "build", "target", "bin", "obj",
    ".gradle", ".m2", ".devsecops", ".idea", ".vscode",
}

# Binary/generated-noise extensions that are never worth text-scanning.
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".bmp", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".pyc", ".class", ".jar",
    ".woff", ".woff2", ".ttf", ".eot",
}

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2MB


def iter_source_files(root: str, extensions: Optional[Set[str]] = None) -> Iterator[Path]:
    """Yield text-scannable files under *root*, optionally filtered to *extensions*.

    *extensions* entries are lowercase with the leading dot, e.g. {".py"}.
    """
    root_path = Path(root).resolve()
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root_path).parts[:-1]):
            continue
        suffix = path.suffix.lower()
        if suffix in SKIP_EXTENSIONS:
            continue
        if extensions is not None and suffix not in extensions:
            continue
        try:
            if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                continue
        except OSError:
            continue
        yield path
