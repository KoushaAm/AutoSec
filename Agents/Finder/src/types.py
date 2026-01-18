# Contains types for other agents to use for the pipeline

from typing import TypedDict, List

class TraceStep(TypedDict, total=False):
    uri: str
    line: int
    message: str # the line of code itself


# One trace/flow has multiple steps (lines)
Trace = List[TraceStep]


# A vulnerability instance can have mutliple flows/traces
class VulnerabilityInstance(TypedDict):
    traces: List[Trace]


class FinderOutput(TypedDict):
    cwe: str                     # e.g. "cwe-078"
    vulnerabilities: List[VulnerabilityInstance]