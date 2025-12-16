# core/types.py
"""
Core type definitions for the Fixer agent.

This module centralizes all shared TypedDicts and dataclasses used across:
- vuln_info.py   (vulnerability metadata)
- prompt_utils.py (prompt assembly)
- context_extractor.py (code context extraction)
- patcher.py     (task wiring)

Keeping types here makes the codebase easier to maintain and reason about.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TypedDict, Mapping, Any


# ================== Core TypedDicts ==================
class ConstraintDict(TypedDict):
    """
    Configuration constraints controlling patch generation limits.
    Enforced by the Patcher when producing diffs.
    """
    max_lines: int
    max_hunks: int
    no_new_deps: bool
    keep_signature: bool


class SinkDict(TypedDict, total=False):
    """Shape for the sink metadata (dangerous call site)."""
    file: str
    line: int
    start_col: int
    end_col: int
    symbol: str


class FlowStepDict(TypedDict, total=False):
    """Shape for one data-flow step (source/propagation)."""
    file: str
    line: int
    note: str


class PoVTestDict(TypedDict, total=False):
    """
    Shape for a Proof-of-Value (PoV) test case the agent can use for feedback.
    """
    name: str
    description: str
    entrypoint: str
    args: List[str]
    env: Dict[str, str]
    expected: Dict[str, object]


class FileSnippetBundle(TypedDict):
    """
    Multi-file snippet bundle structure:

        {
          "by_file": {
            "<repo-relative-path>": "<concatenated snippet text>"
          }
        }

    This is what the Fixer passes into the USER prompt as `vulnerable_snippets`.
    """
    by_file: Dict[str, str]


# ================== Agent metadata container ==================
@dataclass
class AgentFields:
    """
    Metadata describing the vulnerability to patch.

    Required:
        - language: e.g., "Java"
        - function: method name (or "" for global)
        - CWE: identifier string
        - constraints: strongly-typed ConstraintDict
        - sink: SinkDict (primary file & line containing the sink)
        - flow: list of FlowStepDict (source→sink propagation)
        - pov_tests: list of PoVTestDict for guided reasoning

    Optional:
        - vuln_title: human-readable short title
    """
    language: str
    function: str
    CWE: str
    constraints: ConstraintDict
    sink: SinkDict
    flow: List[FlowStepDict] = field(default_factory=list)
    pov_tests: List[PoVTestDict] = field(default_factory=list)
    vuln_title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for prompt assembly."""
        return {
            "language": self.language,
            "function": self.function,
            "CWE": self.CWE,
            "constraints": self.constraints,
            "vuln_title": self.vuln_title,
            "sink": self.sink,
            "flow": self.flow,
            "pov_tests": self.pov_tests,
        }


__all__ = [
    "ConstraintDict",
    "SinkDict",
    "FlowStepDict",
    "PoVTestDict",
    "FileSnippetBundle",
    "AgentFields",
]
