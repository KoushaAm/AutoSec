# constants/vuln_info.py
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

All file paths must be repo-relative. VULN_DIR is a convenience prefix used here.

This file is aligned with the new, strict schema consumed by:
- utils/prompt_utils.AgentFields
- fixer.py (new strict output schema validation)
"""

from typing import List, Dict
from utils.prompt_utils import (
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
)

# In your repo, these example files live under a vulnerable examples folder.
# Adjust this prefix to match your project layout. Finder will pass repo-relative paths
# in production; the Fixer only ever reads files under REPO_ROOT.
VULN_DIR = "Experiments/vulnerable/"


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


# =========================== Example vulnerabilities (from your .java files) ===========================

class CWE_78(VulnerabilityInfo):
    """
    CWE-78: OS Command Injection via Runtime.exec
    File: Experiments/vulnerable/CWE_78.java
    Sink: Runtime.getRuntime().exec(cmd);
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "main"
    CWE: str = "CWE-78"
    VULN_TITLE: str = "Command Injection via Runtime.exec"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 30,
        "max_hunks": 2,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_78.java",
        "line": 13,                     # Runtime.getRuntime().exec(cmd);
        "symbol": "Runtime.exec",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_78.java", "line": 8,  "note": "source: Scanner.nextLine() -> userInput"},
        {"file": f"{VULN_DIR}CWE_78.java", "line": 9,  "note": "propagate: cmd = \"java -version \" + userInput"},
        {"file": f"{VULN_DIR}CWE_78.java", "line": 13, "note": "sink: Runtime.getRuntime().exec(cmd)"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "semicolon_injection",
            "description": "Injects a second command via ';'",
            "entrypoint": "CWE_78#main",
            "args": ["; touch /tmp/pwned"],
            "env": {},
            "expected": {"should_block": True, "no_side_effect_file": "/tmp/pwned"},
        }
    ]


class CWE_22(VulnerabilityInfo):
    """
    CWE-22: Path Traversal in file deletion
    File: Experiments/vulnerable/CWE_22.java
    Sink: f.delete() guarded by naive path.startsWith("/safe_dir/")
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "main"
    CWE: str = "CWE-22"
    VULN_TITLE: str = "Path Traversal in File Deletion"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 30,
        "max_hunks": 2,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_22.java",
        "line": 25,                     # f.delete();
        "symbol": "File.delete",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_22.java", "line": 22, "note": "source: args[0] -> path"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 23, "note": "naive guard: path.startsWith(\"/safe_dir/\")"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 24, "note": "File f = new File(path)"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 25, "note": "sink: f.delete()"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "dotdot_escape",
            "description": "Bypasses naive prefix check via ../",
            "entrypoint": "CWE_22#main",
            "args": ["/safe_dir/../important.dat"],
            "env": {},
            "expected": {"should_block": True, "no_delete": "important.dat"},
        }
    ]


class CWE_94(VulnerabilityInfo):
    """
    CWE-94: Code Injection via ScriptEngine.eval
    File: Experiments/vulnerable/CWE_94.java
    Sink: engine.eval(formula)
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "doGet"
    CWE: str = "CWE-94"
    VULN_TITLE: str = "Code Injection via Expression Evaluation"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 40,
        "max_hunks": 3,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_94.java",
        "line": 22,                     # engine.eval(formula)
        "symbol": "ScriptEngine.eval",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_94.java", "line": 15, "note": "source: request.getParameter(\"formula\")"},
        {"file": f"{VULN_DIR}CWE_94.java", "line": 17, "note": "ScriptEngineManager / engine = JavaScript"},
        {"file": f"{VULN_DIR}CWE_94.java", "line": 22, "note": "sink: engine.eval(formula)"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "evil_formula",
            "description": "Attempts to execute arbitrary code via expression",
            "entrypoint": "CWE_94#doGet",
            "args": [],
            "env": {"QUERY_STRING": "formula=java.lang.Runtime.getRuntime().exec('touch /tmp/pwned')"},
            "expected": {"should_block": True, "no_side_effect_file": "/tmp/pwned"},
        }
    ]


class CWE_918(VulnerabilityInfo):
    """
    CWE-918: SSRF via untrusted host/URL that is base64-decoded and fetched
    File: Experiments/vulnerable/CWE_918.java
    Sink: opening a connection to (decoded) attacker-controlled endpoint
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "fetch"
    CWE: str = "CWE-918"
    VULN_TITLE: str = "SSRF risk via decoded host"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 40,
        "max_hunks": 3,
        "no_new_deps": True,
        "keep_signature": True,
    }

    # The sink is inside fetch() near where a connection is opened and the input stream is read
    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_918.java",
        "line": 41,
        "symbol": "URL.openConnection/getInputStream",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_918.java", "line": 8,  "note": "decodeHost(host): if not http*, Base64-decode"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 20, "note": "encodeHost(host): prepend http:// and Base64-encode"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 35, "note": "fetch(encodedOrPlain): decoded target used for request"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 41, "note": "sink: open connection and read from target"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "metadata_probe",
            "description": "Attempts to reach internal metadata endpoint",
            "entrypoint": "CWE_918#main",
            "args": [],  # uses hardcoded demo flow in main(); adjust if you wire CLI
            "env": {},
            "expected": {"should_block": True, "no_internal_access": True},
        }
    ]
