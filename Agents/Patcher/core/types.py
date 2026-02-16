# core/types.py
"""
Core type definitions for the Patcher agent (Finder-aligned).

This module centralizes shared types used across:
- utils/prompt_utils.py
- core/code_extractor.py
- patcher.py

All naming follows Finder output conventions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TypedDict, Any


# ================== Constraints ==================
class ConstraintDict(TypedDict):
    """
    Patch-generation constraints enforced by the Patcher.
    """
    max_lines: int
    max_hunks: int
    no_new_deps: bool
    keep_signature: bool


# ================== Finder-aligned trace types ==================
class TraceStepDict(TypedDict):
    """
    One step in a source-to-sink trace from Finder.
    """
    uri: str
    line: int
    message: str


Trace = List[TraceStepDict]


# ================== Runtime vulnerability spec ==================
@dataclass
class VulnerabilitySpec:
    """
    Runtime vulnerability specification derived from Finder + Exploiter.

    One instance corresponds to ONE unique vulnerability
    (i.e., one element inside Finder's "vulnerabilities" list).

    Attributes:
        language: e.g., "java"
        cwe_id: Finder-style CWE identifier (e.g., "cwe-022")
        project_name: project identifier used for path prefixing
        constraints: patch-generation constraints
        traces: list of source-to-sink traces (Finder format)
        sink: explicitly stored sink step (derived from traces[0][-1])
        pov_logic: contextual PoV explanation from Exploiter
    """

    language: str
    cwe_id: str
    project_name: str
    constraints: ConstraintDict
    traces: List[Trace] = field(default_factory=list)
    pov_logic: str = ""

    # Derived (guaranteed after __post_init__)
    sink: TraceStepDict = field(init=False)

    def __post_init__(self) -> None:
        """
        Enforce structural guarantees immediately after construction:

        - traces must be non-empty
        - each trace must contain at least one step
        - sink must exist and be consistent across traces
        - each step must include uri/line/message
        - constraints must contain required keys
        - cwe_id must follow finder naming (starts with 'cwe-')
        """
        if not self.cwe_id.startswith("cwe-"):
            raise ValueError(f"cwe_id must be Finder-style like 'cwe-022' (got {self.cwe_id!r})")

        if not self.project_name.strip():
            raise ValueError("project_name must be a non-empty string")

        if not self.traces:
            raise ValueError("VulnerabilitySpec.traces must not be empty")

        first_trace = self.traces[0]
        if not first_trace:
            raise ValueError("Each trace must contain at least one step")

        # Validate step shape + derive sink (last step of first trace)
        self._validate_step(first_trace[-1])
        sink = first_trace[-1]
        sink_uri = sink["uri"]
        sink_line = int(sink["line"])

        for trace in self.traces:
            if not trace:
                raise ValueError("Each trace must contain at least one step")

            last = trace[-1]
            self._validate_step(last)

            if last["uri"] != sink_uri or int(last["line"]) != sink_line:
                raise ValueError("All traces in a vulnerability must share the same sink")

        for key in ("max_lines", "max_hunks", "no_new_deps", "keep_signature"):
            if key not in self.constraints:
                raise ValueError(f"Constraint missing required key: {key}")

        self.sink = sink

    @staticmethod
    def _validate_step(step: TraceStepDict) -> None:
        for k in ("uri", "line", "message"):
            if k not in step:
                raise ValueError(f"Trace step missing required key: {k}")
        # coercible to int
        int(step["line"])

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for prompts or logging."""
        return {
            "language": self.language,
            "cwe_id": self.cwe_id,
            "project_name": self.project_name,
            "constraints": self.constraints,
            "traces": self.traces,
            "sink": self.sink,
            "pov_logic": self.pov_logic,
        }


# ================== Snippet bundle ==================
class FileSnippetBundle(TypedDict):
    """
    Multi-file snippet bundle structure returned by the extractor:

        {
          "by_file": {
            "<repo-relative-path>": "<concatenated snippet text>"
          }
        }
    """
    by_file: Dict[str, str]


__all__ = [
    "ConstraintDict",
    "TraceStepDict",
    "Trace",
    "VulnerabilitySpec",
    "FileSnippetBundle",
]
