from typing import TypedDict, Dict, Any, Optional
import logging
import uuid
import argparse
import subprocess
import json
from langgraph.graph import StateGraph, END, START

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("autossec.langgraph")

class AutoSecState(TypedDict, total=False):
    project_name: Optional[str]         # ex: jenkinsci__perfecto-plugin_CVE
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    artifacts: Optional[Dict[str, str]]
    exploiter: Optional[Dict[str, Any]]
    patcher: Optional[Dict[str, Any]]
    verifier: Optional[Dict[str, Any]]

def build_workflow() -> Any:
    graph = StateGraph(AutoSecState)
    graph.add_node("finder", finder_node)
    graph.add_node("exploiter", exploiter_node)
    graph.add_node("patcher", patcher_node)
    graph.add_node("verifier", verifier_node)

    # linear edges
    graph.add_edge(START, "finder")
    graph.add_edge("finder", "exploiter")
    graph.add_edge("exploiter", "patcher")
    graph.add_edge("patcher", "verifier")
    graph.add_edge("verifier", END)

    workflow = graph.compile()
    return workflow


def get_db() -> dict:
    # function to pull vulnerabilties from database
    return [] # returns json object

def push_db() -> tuple[int, str]:
    # function to push vulnerabilities into the database
    return (400, "Failed")



def finder_node(state: AutoSecState) -> AutoSecState:
    logger.info("Finder started")

    project_name = state["project_name"]
    query = state["vuln_id"]

    # 1. run IRIS
    subprocess.run(["python3", "./Agents/Finder/scripts/build_and_analyze.py",
        "--project-name", project_name,
        "--zip-path", f"/home/vvv/AutoSec/AutoSec/Projects/{project_name}.zip",
        "--query", query,
    ], check=True)

    # 2. Load IRIS output
    sarif_path = f"/home/vvv/AutoSec/AutoSec/Experiments/Finder/output/{project_name}/test/{query}-posthoc-filter/results.sarif"
    with open(sarif_path) as f:
        findings = json.load(f)

    # 3. Save results into pipeline state
    state["vuln"] = findings



def exploiter_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: exploiter started")
    return state


def patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: patcher started")
    return state


def verifier_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: verifier started")
    return state


if __name__ == "__main__":
      # INITIAL INPUT STATE
    initial_state: AutoSecState = {
        "project_slug": "perwendel__spark_CVE-2018-9159_2.7.1",
        "vuln_id": "cwe-022wLLM",
    }

    workflow = build_workflow()

    # Execute the graph
    final_state = workflow.invoke(initial_state)

    print("\n==========\nPIPELINE COMPLETE")
    print(json.dumps(final_state, indent=2))