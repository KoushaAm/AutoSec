import json
from typing import TypedDict, List, Any, Dict


# TypedDict Definitions
class TraceStep(TypedDict, total=False):
    uri: str
    line: int
    message: str

Trace = List[TraceStep]

class VulnerabilityInstance(TypedDict):
    traces: List[Trace]

class FinderOutput(TypedDict):
    cwe_id: str
    vulnerabilities: List[VulnerabilityInstance]


# Loader + Validator
def load_dummy_finder_output(json_path: str) -> FinderOutput:
    """
    Load a JSON file and validate that it matches the expected FinderOutput schema.
    
    Raises:
        ValueError if structure is invalid.
    """
    print(f"====== Loading Injected Finder output from: {json_path} ======")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _validate_finder_output(data)

    return data  # type: ignore


# Internal Validation
def _validate_finder_output(data: Dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("FinderOutput must be a dictionary.")

    if "cwe_id" not in data or not isinstance(data["cwe_id"], str):
        raise ValueError("Missing or invalid 'cwe_id'.")

    if "vulnerabilities" not in data or not isinstance(data["vulnerabilities"], list):
        raise ValueError("Missing or invalid 'vulnerabilities' list.")

    for vuln in data["vulnerabilities"]:
        if not isinstance(vuln, dict):
            raise ValueError("Each vulnerability must be a dictionary.")

        if "traces" not in vuln or not isinstance(vuln["traces"], list):
            raise ValueError("Each vulnerability must contain a 'traces' list.")

        for trace in vuln["traces"]:
            if not isinstance(trace, list):
                raise ValueError("Each trace must be a list of TraceSteps.")

            for step in trace:
                if not isinstance(step, dict):
                    raise ValueError("Each TraceStep must be a dictionary.")

                if "uri" not in step or not isinstance(step["uri"], str):
                    raise ValueError("TraceStep missing or invalid 'uri'.")

                if "line" not in step or not isinstance(step["line"], int):
                    raise ValueError("TraceStep missing or invalid 'line'.")

                if "message" not in step or not isinstance(step["message"], str):
                    raise ValueError("TraceStep missing or invalid 'message'.")
