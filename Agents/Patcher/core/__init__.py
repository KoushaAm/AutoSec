# Agents/Patcher/core/__init__.py
"""
Core package for the Patcher system.

This package contains:
- types.py          : shared TypedDicts and dataclasses (Finder-aligned)
- code_extractor.py : code context extraction logic (trace-driven, fail-fast)
- method_locator/   : language-specific method boundary discovery (Tree-sitter)
"""

from .types import (
    ConstraintDict,
    TraceStepDict,
    Trace,
    VulnerabilitySpec,
    FileSnippetBundle,
)

from .code_extractor import (
    extract_snippets_for_vuln,
    SnippetExtractionError,
)

__all__ = [
    "ConstraintDict",
    "TraceStepDict",
    "Trace",
    "VulnerabilitySpec",
    "FileSnippetBundle",
    "extract_snippets_for_vuln",
    "SnippetExtractionError",
]
