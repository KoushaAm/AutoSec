from typing import TypedDict, Dict, Any, Optional, List
import json
import subprocess
import os
import uuid
import argparse
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command

# local imports
from . import logger
from Agents.Patcher import patcher_main
from Agents.Finder.src.types import FinderOutput
from Agents.Finder.src.output_converter import sarif_to_finder_output

class AutoSecState(TypedDict, total=False):
    project_name: Optional[str]         # ex: jenkinsci__perfecto-plugin_CVE
    language: Optional[str]
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    finder_output: Optional[List[FinderOutput]]
    artifacts: Optional[Dict[str, str]]
    exploiter: Optional[Dict[str, Any]]
    patcher: Optional[Dict[str, Any]]
    verifier: Optional[Dict[str, Any]]

def _build_workflow() -> Any:
    graph = StateGraph(AutoSecState)
    graph.add_node("finder", _finder_node)
    graph.add_node("exploiter", _exploiter_node)
    graph.add_node("patcher", _patcher_node)
    graph.add_node("verifier", _verifier_node)

    # linear edges
    graph.add_edge(START, "finder")
    graph.add_edge("finder", "exploiter")
    graph.add_edge("patcher", "verifier")

    # conditional edges
    # exploiter -> finder OR exploiter -> patcher
    # verifier -> finder OR verifier -> end

    workflow = graph.compile()
    return workflow

def get_db() -> dict:
    # function to pull vulnerabilities from database
    return [] # returns json object

def push_db() -> tuple[int, str]:
    # function to push vulnerabilities into the database
    return (400, "Failed")



def _finder_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - finder started")

    project_name = state["project_name"]
    query = state["vuln_id"] + "wLLM"

    # 1. setup command to have IRIS inside docker container
    docker_cmd = [
        "docker", "run",
        "--platform=linux/amd64",
        "--rm",
        "-v", "/home/vinci/AutoSec/Projects:/workspace/Projects",
        "-v", "/home/vinci/AutoSec/Agents:/workspace/Agents",
        "-w", "/workspace/Agents/Finder",
        "iris:latest",
        "bash", "-lc",
        f"source /opt/conda/etc/profile.d/conda.sh && conda activate iris && "
        f"python3 ./scripts/build_and_analyze.py "
        f"--project-name {project_name} "
        f"--zip-path /workspace/Projects/{project_name}.zip "
        f"--query {query}"
    ]

    logger.info(f"Running IRIS inside Docker for project {project_name}")

    # 2. Run IRIS analysis
    try:
        subprocess.run(docker_cmd, check=True, text=True)

    # analysis failed for some reason
    except subprocess.CalledProcessError as e:
            print("Finder failed with an error")
            print("Return code:", e.returncode)
            print("stdout:", e.stdout)
            print("stderr:", e.stderr)

            state["finder_output"] = None
            state["vuln"] = None
            return state

    # 3. Load IRIS output
    sarif_path = f"./Agents/Finder/output/{project_name}/test/{query}-posthoc-filter/results.sarif"
    try:
        with open(sarif_path) as f:
            findings = json.load(f)

        # 4. Save results into pipeline state
        state["finder_output"] = sarif_to_finder_output(findings, cwe=state["vuln_id"])
        state["vuln"] = findings # keep oringial json dump just in case its needed

    # no vulnerabilites were found
    except FileNotFoundError:
        print("Finder found no vulnerabilites")
        state["finder_output"] = None
        state["vuln"] = None

    return state



def _exploiter_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: exploiter started")

    retry_finder = False
    new_state = dict(state)

    if retry_finder:
        return Command(
            goto="finder",
            update=new_state
        )

    # continue linearly to patcher
    return Command(
        goto="patcher",
        update=new_state
    )



def _patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - patcher started")

    success = patcher_main()
    state["patcher"] = {"success": success}

    return state


def _verifier_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: verifier started")

    retry_finder = False
    new_state = dict(state)

    if retry_finder:
        return Command(
            goto="finder",
            update=new_state
        )

    # finish pipeline
    return Command(
        goto=END,
        update=new_state
    )


# ====== Execute workflow =====
def pipeline_main():
    # INITIAL INPUT STATE
    initial_state: AutoSecState = {
        "project_name": "perwendel__spark_CVE-2018-9159_2.7.1",
        "vuln_id": "cwe-022",
        "language": "python",
    }

    workflow = _build_workflow()

    # Execute the graph
    final_state = workflow.invoke(initial_state)

    print("\n====== STATE DUMP ======")
    print(json.dumps(final_state, indent=2))
    print("======^==========^======\n")


# standalone execution
if __name__ == "__main__":
    pipeline_main()