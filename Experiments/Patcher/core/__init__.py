# core/__init__.py
"""
Core package for the Patcher/Fixer system.

This package contains:
- types.py          : shared TypedDicts and dataclasses (AgentFields, etc.)
- code_extractor.py : code context extraction logic (method/data-flow based)
- method_locator/   : language-specific method boundary discovery
"""

from .types import (
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
    FileSnippetBundle,
    AgentFields,
)

from .code_extractor import build_method_flow_snippets

__all__ = [
    "ConstraintDict",
    "SinkDict",
    "FlowStepDict",
    "PoVTestDict",
    "FileSnippetBundle",
    "AgentFields",
    "build_method_flow_snippets",
]
