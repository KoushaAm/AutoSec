# core/__init__.py
"""
Core package for the Patcher/Fixer system.

This package contains:
- types.py            : shared TypedDicts and dataclasses (AgentFields, etc.)
- context_extractor.py: code context extraction logic
- method_locator/     : language-specific method boundary discovery
"""

from .types import (
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
    FileSnippetBundle,
    AgentFields,
)

__all__ = [
    "ConstraintDict",
    "SinkDict",
    "FlowStepDict",
    "PoVTestDict",
    "FileSnippetBundle",
    "AgentFields",
]
