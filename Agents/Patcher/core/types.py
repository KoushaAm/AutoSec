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
    language: str
    cwe_id: str
    project_name: str
    constraints: ConstraintDict
    traces: List[Trace] = field(default_factory=list)
    pov_logic: str = ""

    sink: TraceStepDict = field(init=False)

    def __post_init__(self) -> None:
        """
        Enforce structural guarantees immediately after construction:

        - traces must be non-empty (AFTER cleaning)
        - each trace must contain at least one step
        - sink must exist and be consistent across traces
        - each step must include uri/line/message
        - constraints must contain required keys
        - cwe_id must follow finder naming (starts with 'cwe-')
        """
        if not self.cwe_id.startswith("cwe-"):
            raise ValueError(
                f"cwe_id must be Finder-style like 'cwe-022' (got {self.cwe_id!r})"
            )

        if not self.project_name.strip():
            raise ValueError("project_name must be a non-empty string")

        # clean traces before enforcing non-empty
        self.traces = self._clean_traces(self.traces)

        if not self.traces:
            raise ValueError("VulnerabilitySpec.traces must not be empty")

        first_trace = self.traces[0]
        if not first_trace:
            # Shouldn't happen after cleaning, but keep defensive
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
        int(step["line"])  # coercible to int

    @classmethod
    def _clean_traces(cls, traces: Any) -> List[Trace]:
        """
        Remove empty/invalid traces.

        Rules:
        - If traces is not a list -> return []
        - Keep only items that are lists (a Trace)
        - Drop empty traces
        - Optionally: drop invalid steps inside traces (if a step is missing keys or line not int-able)
        - Drop traces that become empty after step filtering
        """
        if not isinstance(traces, list):
            return []

        cleaned: List[Trace] = []
        for t in traces:
            if not isinstance(t, list) or not t:
                continue

            # Filter steps to only valid TraceStepDict-shaped entries
            valid_steps: Trace = []
            for step in t:
                if not isinstance(step, dict):
                    continue
                if not all(k in step for k in ("uri", "line", "message")):
                    continue
                try:
                    int(step["line"])
                except Exception:
                    continue
                valid_steps.append(step)  # type: ignore[arg-type]

            if valid_steps:
                cleaned.append(valid_steps)

        return cleaned

    def to_dict(self) -> Dict[str, Any]:
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
