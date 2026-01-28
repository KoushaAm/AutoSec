from .types import FinderOutput, VulnerabilityInstance, TraceStep, Trace
from typing import Dict, Any, List

def _safe_get(d: Any, *keys: str) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur

def _parse_thread_flow_location(tfl: Dict[str, Any]) -> TraceStep:
    loc = tfl.get("location", {})
    step: TraceStep = {}

    # message text
    msg = _safe_get(loc, "message", "text")
    if isinstance(msg, str):
        step["message"] = msg

    # file uri
    uri = _safe_get(loc, "physicalLocation", "artifactLocation", "uri")
    if isinstance(uri, str):
        step["uri"] = uri

    # line number
    line = _safe_get(loc, "physicalLocation", "region", "startLine")
    if isinstance(line, int):
        step["line"] = line

    return step


def sarif_to_finder_output(sarif: Dict[str, Any], *, cwe_id: str) -> FinderOutput:
    vulnerabilities: List[VulnerabilityInstance] = []

    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            traces: List[Trace] = []

            for code_flow in result.get("codeFlows", []):
                for thread_flow in code_flow.get("threadFlows", []):
                    trace: Trace = []

                    for tfl in thread_flow.get("locations", []):
                        if not isinstance(tfl, dict):
                            continue

                        step = _parse_thread_flow_location(tfl)
                        if step:
                            trace.append(step)

                    if trace:
                        traces.append(trace)

            # One VulnerabilityInstance == one SARIF result
            vulnerabilities.append(
                VulnerabilityInstance(traces=traces)
            )

    return FinderOutput(
        cwe_id=cwe_id,
        vulnerabilities=vulnerabilities,
    )
