# Patcher/constants/vuln_info.py
"""
Vulnerability definitions (new format, no legacy).
Each vulnerability is a class that is validated at import time by VulnerabilityInfo.__init_subclass__.

Required class attributes:
  LANGUAGE: str
  FUNC_NAME: str                # "" if N/A
  CWE: str
  CONSTRAINTS: ConstraintDict   # max_lines, max_hunks, no_new_deps, keep_signature
  SINK: SinkDict                # must include at least file + line
  FLOW: list[FlowStepDict]      # [] if none (each step needs file + line)
  POV_TESTS: list[PoVTestDict]  # [] if none
Optional:
  VULN_TITLE: str

All file paths must be repo-relative (from BASE_DIR).

This file is aligned with the new, strict schema consumed by:
- utils/prompt_utils.AgentFields
- fixer.py (new strict output schema validation)
"""

from typing import List, Dict
# local imports
from ..core import (
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
)

class VulnerabilityInfo:
    """
    Base class enforcing the new, strict attribute contract at class creation.
    No Enum .value usage — attributes are plain Python values.

    Any subclass missing required attributes or with malformed dict/list shapes
    will raise at import time, preventing bad definitions from reaching the Fixer.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        required: Dict[str, type] = {
            "LANGUAGE": str,
            "FUNC_NAME": str,
            "CWE": str,
            "CONSTRAINTS": dict,  # validated structurally below
            "SINK": dict,
            "FLOW": list,
            "POV_TESTS": list,
        }
        for name, expected_type in required.items():
            if not hasattr(cls, name):
                raise TypeError(f"{cls.__name__} is missing required attribute: {name}")
            value = getattr(cls, name)
            if name in ("CONSTRAINTS", "SINK"):
                if not isinstance(value, dict):
                    raise TypeError(f"{cls.__name__}.{name} must be a dict-like structure")
            elif not isinstance(value, expected_type):
                raise TypeError(f"{cls.__name__}.{name} must be of type {expected_type.__name__}")

        # Structural checks for expected keys in dict-like shapes
        constraints: ConstraintDict = getattr(cls, "CONSTRAINTS")
        for key in ("max_lines", "max_hunks", "no_new_deps", "keep_signature"):
            if key not in constraints:
                raise TypeError(f"{cls.__name__}.CONSTRAINTS missing key: {key}")

        sink: SinkDict = getattr(cls, "SINK")
        if "file" not in sink or "line" not in sink:
            raise TypeError(f"{cls.__name__}.SINK must include 'file' and 'line'")

        # FLOW entries must each have file + line
        flow: List[FlowStepDict] = getattr(cls, "FLOW")
        for index, step in enumerate(flow, start=1):
            if "file" not in step or "line" not in step:
                raise TypeError(f"{cls.__name__}.FLOW[{index}] must include 'file' and 'line'")

        # POV_TESTS: list (can be empty)
        pov_tests: List[PoVTestDict] = getattr(cls, "POV_TESTS")
        if not isinstance(pov_tests, list):
            raise TypeError(f"{cls.__name__}.POV_TESTS must be a list")

        # Optional title type check
        if hasattr(cls, "VULN_TITLE") and not isinstance(getattr(cls, "VULN_TITLE"), str):
            raise TypeError(f"{cls.__name__}.VULN_TITLE must be a string if provided")