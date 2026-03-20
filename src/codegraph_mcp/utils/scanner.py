"""Lazy, generator-based repository file scanner."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Generator

logger = logging.getLogger("codegraph_mcp.scanner")

# Extensions we know how to parse
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
}

# Directories to always skip
SKIP_DIRS: set[str] = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    "target",
}


def scan_repository(
    root: Path,
    *,
    extensions: set[str] | None = None,
) -> Generator[Path, None, None]:
    """Yield source files lazily from *root*, skipping ignored directories.

    Parameters
    ----------
    root:
        Repository root directory.
    extensions:
        If given, only yield files whose suffix is in this set.
        Defaults to ``SUPPORTED_EXTENSIONS.keys()``.
    """
    if extensions is None:
        extensions = set(SUPPORTED_EXTENSIONS.keys())

    root = root.resolve()
    if not root.is_dir():
        logger.error("Repository path is not a directory: %s", root)
        return

    logger.info("Scanning repository: %s", root)
    file_count = 0

    for item in _walk(root):
        if item.suffix in extensions:
            file_count += 1
            if file_count % 500 == 0:
                logger.info("Scanned %d files so far …", file_count)
            yield item

    logger.info("Scan complete — %d source files found.", file_count)


def _walk(directory: Path) -> Generator[Path, None, None]:
    """Recursively walk *directory*, skipping SKIP_DIRS."""
    try:
        entries = sorted(directory.iterdir())
    except PermissionError:
        logger.warning("Permission denied: %s", directory)
        return

    for entry in entries:
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            yield from _walk(entry)
        elif entry.is_file():
            yield entry


def detect_language(path: Path) -> str | None:
    """Return language identifier for a file, or None if unsupported."""
    return SUPPORTED_EXTENSIONS.get(path.suffix)
