# core/method_locator/__init__.py
"""
Language-agnostic method locator interface and factory.

A MethodLocator maps (file, line) -> MethodInfo, where MethodInfo
captures the bounds and identity of the enclosing method/function.

Concrete implementations live in language-specific modules, e.g.:
- core/method_locator/java_method_locator.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, List, Optional


@dataclass(frozen=True)
class MethodInfo:
    """
    Metadata about a single method/function in a source file.

    Attributes:
        name:       Simple method name (e.g., 'main', 'doGet')
        start_line: 1-based start line of the declaration node (inclusive)
        end_line:   1-based end line of the declaration node (inclusive)
        signature:  Best-effort textual representation of the declaration
        file:       Path to the file (repo-relative, not absolute)
    """
    name: str
    start_line: int
    end_line: int
    signature: str
    file: Path


class MethodLocator(Protocol):
    """
    Protocol for language-specific method locators.

    Implementations are responsible for:
      - indexing source files to discover method boundaries
      - resolving a MethodInfo for a given (file, line) pair
    """

    def index_file(self, file_path: Path) -> List[MethodInfo]:
        """Parse and index a single source file, returning its methods."""
        ...

    def find_method_for_line(self, file_path: Path, line: int) -> Optional[MethodInfo]:
        """
        Return the MethodInfo whose [start_line, end_line] contains `line`,
        or None if the line is not inside any method.
        """
        ...


def get_method_locator(language: str, repo_root: Path) -> MethodLocator:
    """
    Factory for language-specific MethodLocator implementations.

    Currently supported:
        - "java" (case-insensitive)

    Args:
        language: Language tag (e.g., "java", "Java")
        repo_root: Repository root (used for resolving relative paths).

    Returns:
        A MethodLocator instance for the given language.

    Raises:
        ValueError if the language is not supported.
    """
    lang_norm = language.strip().lower()

    # Lazy imports to avoid hard dependencies at import time.
    if lang_norm == "java":
        from .java_method_locator import JavaMethodLocator

        return JavaMethodLocator(repo_root=repo_root)

    raise ValueError(f"No MethodLocator implementation available for language: {language!r}")


__all__ = [
    "MethodInfo",
    "MethodLocator",
    "get_method_locator",
]
