# Pipeline/utils.py
import json
from typing import TypedDict, List, Any, Dict, Optional
from pathlib import Path
from datetime import datetime, timezone

from Pipeline.project_variants import ProjectVariants


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

#* =============== Exploiter Utilities =============== *#
def has_actionable_vulnerabilities(finder_output: Optional[Dict[str, Any]]) -> bool:
    """
    Returns True if finder_output contains at least one vulnerability
    with non-empty traces. Otherwise returns False.

    Handles:
    - finder_output is None
    - vulnerabilities missing
    - empty vulnerabilities list
    - vulnerabilities with empty or invalid traces
    """
    if not finder_output:
        return False

    vulnerabilities = finder_output.get("vulnerabilities")
    if not isinstance(vulnerabilities, list) or len(vulnerabilities) == 0:
        return False

    return any(
        isinstance(vuln, dict)
        and isinstance(vuln.get("traces"), list)
        and len(vuln["traces"]) > 0
        for vuln in vulnerabilities
    )


def parse_exploiter_report(report_data) -> tuple[bool, list[str], str]:
    """Return (exploitable, pov_test_paths, pov_logic) from a loaded report.json."""
    if isinstance(report_data, dict):
        entries = [report_data]
    elif isinstance(report_data, list):
        entries = report_data
    else:
        raise TypeError(f"Unexpected report.json top-level type: {type(report_data)}")

    exploitable = any(isinstance(e, dict) and e.get("exploitable") for e in entries)

    pov_test_paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        paths = entry.get("pov_test_path", [])
        if isinstance(paths, str):
            paths = [paths]
        pov_test_paths.extend(p for p in paths if isinstance(p, str))

    pov_logic = ""
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        logic = entry.get("pov_logic", "")
        if isinstance(logic, str):
            pov_logic = logic

    return exploitable, pov_test_paths, pov_logic


#* =============== Dummy Data Loaders & Validators =============== *#
# Loader + Validator
def load_dummy_finder_output(json_path: str) -> Optional[FinderOutput]:
    """
    Load a JSON file and validate that it matches the expected FinderOutput schema.

    Returns None if the file does not exist, so the Finder node can run normally.
    Raises ValueError if the file exists but its structure is invalid.
    """
    if not Path(json_path).exists():
        print(f"====== No injected Finder output at {json_path} — Finder will run ======")
        return None
    
    print(f"====== Loading Injected Finder output from: {json_path} ======")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _validate_finder_output(data)

    return data  # type: ignore


def load_dummy_patcher_output(AGENTS_DIR: Path, SELECTED_PROJECT: ProjectVariants) -> str:
    patcher_output_base = AGENTS_DIR / "Patcher" / "output"
    patcher_dirs = sorted(patcher_output_base.glob(f"patcher_{SELECTED_PROJECT.project_name}_datetime_*"))
    if not patcher_dirs:
        raise FileNotFoundError(f"No patcher output found for {SELECTED_PROJECT.project_name} in {patcher_output_base}")
    patcher_artifact_path = str(patcher_dirs[-1])  # latest run
    print(f"Using patcher output: {patcher_artifact_path}")
    return patcher_artifact_path


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


def save_state_dump(state: Dict[str, Any], output_dir: str = "Pipeline/output") -> str:
    """
    Save the pipeline final state to a timestamped JSON file.

    Args:
        state: The final pipeline state
        output_dir: Directory to store dumps

    Returns:
        Path to the saved file (string)
    """
    print("\n====== STATE DUMP ======")
    print(json.dumps(state, indent=2, default=str))
    print("======^==========^======\n")

    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        raw_project_name = state.get("project_name")
        project_name = str(raw_project_name).strip() if raw_project_name is not None else ""
        if not project_name:
            project_name = "unknown_project"
        project_name = project_name.replace("/", "_").replace("\\", "_")

        file_path = output_path / f"{raw_project_name}_state_dump_{timestamp}.json"

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)

        return str(file_path)

    except Exception as e:
        print(f"[utils.save_state_dump] Failed to save state: {e}")
        return ""