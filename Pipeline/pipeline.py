from enum import Enum
from typing import TypedDict, Dict, Any, Optional, List
import json
import subprocess
import os
import uuid
import argparse
import sys
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command
from pathlib import Path

# from Agents.Exploiter.data.primevul.setup import project_slug
# local imports
from . import logger
from Agents.Patcher import patcher_main
from Agents.Verifier import verifier_main
from Agents.Finder.src.types import FinderOutput
from Agents.Finder.src.output_converter import sarif_to_finder_output
from datetime import datetime

# relative path information
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = (BASE_DIR / "Projects").resolve()
AGENTS_DIR   = (BASE_DIR / "Agents").resolve()

class AutoSecState(TypedDict, total=False):
    project_name: Optional[str]         # ex: jenkinsci__perfecto-plugin_CVE
    language: Optional[str]
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    finder_model: Optional[str]
    finder_reanalyze: Optional[bool]
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
    # graph.add_edge("finder", "exploiter")
    graph.add_edge("finder", "patcher")
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

    # make sure Project/Sources folder exists
    Path(PROJECTS_DIR / "Sources").mkdir(exist_ok=True)

    host_ws = os.environ.get("HOST_WORKSPACE")
    if not host_ws:
        raise RuntimeError("HOST_WORKSPACE env var not set. Add it in devcontainer.json.")
    host_ws = host_ws.replace("\\", "/") # for windows compatibility

    # get relevant args from autosecstate
    project_name = state["project_name"]
    query = state["vuln_id"] + "wLLM"
    model = state["finder_model"]

    # setup args for build_and_analyze.py script. make sure project if project is reanalyzed, use --overwrite and no need to unzip folder
    build_and_analyze_args = f"--project-name {project_name} --query {query} --model {model} "
    if state["finder_reanalyze"]:
        build_and_analyze_args += f"--overwrite"
    else:
        build_and_analyze_args += f"--zip-path /workspace/Projects/Zipped/{project_name}.zip"

    print(f"\n---- ARGS: {build_and_analyze_args} ----\n")

    # 1. setup command to have IRIS inside docker container
    docker_cmd = [
        "docker", "run",
        "--platform=linux/amd64",
        "--rm",
        "-v", f"{host_ws}/Projects:/workspace/Projects",
        "-v", f"{host_ws}/Agents:/workspace/Agents",
        "-w", "/workspace/Agents/Finder",
        "iris:latest",
        "bash", "-lc",
        "source /opt/conda/etc/profile.d/conda.sh && conda activate iris && "
        "python3 ./scripts/build_and_analyze.py " + build_and_analyze_args
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
            state["finder_reanalyze"] = False
            return state

    # 3. Load IRIS output
    sarif_path = f"./Agents/Finder/output/{project_name}/test/{query}-posthoc-filter/results.sarif"
    try:
        with open(sarif_path) as f:
            findings = json.load(f)

        # 4. Save results into pipeline state
        state["finder_output"] = sarif_to_finder_output(findings, cwe_id=state["vuln_id"])
        state["vuln"] = findings # keep oringial json dump just in case its needed

    # no vulnerabilites were found
    except FileNotFoundError:
        print("Finder found no vulnerabilites")
        state["finder_output"] = None
        state["vuln"] = None

    state["finder_reanalyze"] = False
    return state


def _exploiter_node(state: AutoSecState) -> Command:
    logger.info("Node: exploiter started")

    # saving vulnerabilities json into result.json in exploiter's project directory
    raw_vuln_dir = os.path.join(os.getcwd(), "Agents", "Exploiter", "vuln_agent", "modules", "data", "raw", "result.json")
    print("raw_vuln_dir", raw_vuln_dir)

    # TODO: UNCOMMENT THIS WHEN FINDER IS RUNNING AND stat["vuln"] exists
    # vuln_data = state.get("vuln", None)

    # if not vuln_data:
    #     logger.error("Vulnerability data not found")
    #     return Command(goto=END, update=state)

    # with open(raw_vuln_dir, "w") as f:
    #     f.write(json.dumps(vuln_data))

    # taking a copy of the state
    new_state = dict(state)
    project_name = new_state.get("project_name")
    if not project_name:
        raise ValueError("project_name missing from state")

    exploiter_dir = os.path.join(os.getcwd(), "Agents", "Exploiter")
    exploiter_main = os.path.join(exploiter_dir, "main.py")

    if not os.path.exists(exploiter_main):
        raise FileNotFoundError(f"Exploiter entrypoint not found: {exploiter_main}")

    # Execution
    run_cmd = [
        sys.executable,
        "main.py",
        "--dataset", "cwe-bench-java",
        "--project", project_name,
        "--model", "gpt5",
        "--budget", "5.0",
        "--timeout", "3600",
        "--no_branch",
        "--verbose",
    ]

    try:
        subprocess.run(run_cmd, cwd=exploiter_dir, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Exploiter subprocess failed (exit={e.returncode}).")
        return Command(goto=END, update=new_state)

    # opening exploiter report to decide what to do next
    report_path = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "workdir_no_branch",
        "project-sources",
        project_name,
        "report.json",
    )

    if not os.path.exists(report_path):
        logger.error(f"Exploiter report not found: {report_path}")
        return Command(goto=END, update=new_state)

    with open(report_path, "r") as f:
        report_data = json.load(f)

    # here we check if vulnerability exploitation was successful
    if isinstance(report_data, dict):
        exploitable = bool(report_data.get("exploitable", False))
    elif isinstance(report_data, list):
        # try last entry as "final report"
        exploitable = False
        if report_data and isinstance(report_data[-1], dict) and "exploitable" in report_data[-1]:
            exploitable = bool(report_data[-1].get("exploitable", False))
        else:
            # fallback: any entry marks exploitable
            exploitable = any(isinstance(x, dict) and x.get("exploitable") for x in report_data)
    else:
        raise TypeError(f"Unexpected report.json top-level type: {type(report_data)}")

    try :
        new_state["exploiter"] = {
            "success": exploitable,
            "report_path": report_path,
        }

    except Exception as e:
        logger.error(f"Exploiter subprocess failed (exit={e.returncode}).")

    if not exploitable:
        logger.warning("Exploiter ran but did not find an exploitable PoV.")
        new_state["finder_reanalyze"] = True
        return Command(goto="finder", update=new_state)

    logger.info("Vulnerability exploited! Continuing to patcher.")
    state["exploiter"] = new_state

    # print(state["exploiter"])

    return Command(goto="patcher", update=new_state)


def _patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - patcher started")

    if not state.get("language"):
        raise ValueError("language missing from state")

    if not state.get("project_name"):
        raise ValueError("project_name missing from state")

    if not state.get("finder_output"):
        raise ValueError("finder_output missing from state")

    # if not state.get("exploiter"):
        # raise ValueError("exploiter output missing from state")

    # state["exploiter"]["pov_logic"]

    # TODO: update with exploiter pov_logic when accessible
    pov_logic = "Example PoV logic from exploiter report"

    success, run_dir = patcher_main(
            language=state["language"],
            cwe_id=state['finder_output']['cwe_id'],
            vulnerability_list=state['finder_output']['vulnerabilities'],
            project_name=state["project_name"],
            pov_logic=pov_logic,
            save_prompt=True,
        )

    state["patcher"] = {"success": success, "artifact_path": run_dir}

    return state


def _verifier_node(state: AutoSecState) -> Command:
    logger.info("Node: verifier started")
    
    new_state = dict(state)
    
    try:
        patcher_data = state.get("patcher", {})
        patcher_output_path = patcher_data.get("output_path")
        
        if not patcher_output_path:
            logger.error("No patcher output_path in state - Patcher must set state['patcher']['output_path']")
            new_state["verifier"] = {
                "success": False,
                "error": "Patcher output path not provided in state",
                "patches_verified": 0
            }
            return Command(goto=END, update=new_state)
        
        # get Exploiter's report.json path
        exploiter_data = state.get("exploiter", {})
        exploiter_report_path = exploiter_data.get("report_path")
        
        # load Patcher's manifest
        logger.info(f"Loading Patcher output: {patcher_output_path}")
        with open(patcher_output_path, "r") as f:
            patcher_manifest = json.load(f)
        
        # load Exploiter's POV tests if available
        pov_tests = None
        if exploiter_report_path and os.path.exists(exploiter_report_path):
            logger.info(f"Loading POV tests from Exploiter: {exploiter_report_path}")
            with open(exploiter_report_path, "r") as f:
                report_data = json.load(f)
            
            # extract POV tests from Exploiter report
            if isinstance(report_data, list):
                pov_tests = report_data
            elif isinstance(report_data, dict):
                pov_tests = [report_data]
            
            logger.info(f"Found {len(pov_tests) if pov_tests else 0} POV test(s) from Exploiter")
            
            # inject POV tests into each patch in Patcher's manifest
            for patch in patcher_manifest.get("patches", []):
                patch["pov_tests"] = pov_tests
            
            # save updated manifest in Agents/Verifier/output/ directory
            verifier_output_dir = BASE_DIR / "Agents" / "Verifier" / "output"
            verifier_output_dir.mkdir(parents=True, exist_ok=True)
            
            # timestamped filename for the merged manifest
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            updated_manifest_path = verifier_output_dir / f"manifest_with_pov_{timestamp}.json"
            
            with open(updated_manifest_path, "w") as f:
                json.dump(patcher_manifest, f, indent=2)
            
            patcher_output_path = str(updated_manifest_path)
            logger.info(f"Saved merged manifest to: {patcher_output_path}")
        
        # run Verifier with the updated manifest
        logger.info(f"Running Verifier on: {patcher_output_path}")
        verification_results = verifier_main(input_path=patcher_output_path, use_latest=False)
        
        new_state["verifier"] = verification_results
        
        # summary log
        if verification_results.get("success"):
            total = verification_results.get("patches_verified", 0)
            passed = verification_results.get("passed", 0)
            failed = verification_results.get("failed", 0)
            
            logger.info(f"Verifier completed: {passed}/{total} patches passed, {failed} failed")
            
            # TODO: Implement feedback loops
            # - If patches PASSED → goto="finder" (find more vulnerabilities)
            # - If patches FAILED → goto="patcher" (generate better patches)
            # For now: linear pipeline ends here
            
            logger.info("Verification complete. Pipeline finished (feedback loops not yet implemented).")
            return Command(goto=END, update=new_state)
        else:
            # Verification encountered an error
            error = verification_results.get("error", "Unknown error")
            logger.error(f"Verifier failed: {error}")
            return Command(goto=END, update=new_state)
            
    except Exception as e:
        logger.error(f"Verifier node encountered exception: {e}")
        new_state["verifier"] = {
            "success": False,
            "error": str(e),
            "patches_verified": 0
        }
        return Command(goto=END, update=new_state)

# ====== Project Variants ======
class ProjectVariant(Enum):
    CODEHAUS_2018 = {
        "name": "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5",
        "cwe_id": "cwe-022"
    }
    CODEHAUS_2017 = {
        "name": "codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15",
        "cwe_id": "cwe-078"
    }
    NAHSRA = {
        "name": "nahsra__antisamy_CVE-2016-10006_1.5.3",
        "cwe_id": "cwe-079"
    }
    PERWENDEL_2018 = {
        "name": "perwendel__spark_CVE-2018-9159_2.7.1",
        "cwe_id": "cwe-022"
    }

    @property
    def project_name(self) -> str:
        return self.value["name"]

    @property
    def cwe_id(self) -> str:
        return self.value["cwe_id"]

# ====== Execute workflow =====
def pipeline_main():
    SELECTED_PROJECT = ProjectVariant.CODEHAUS_2018
    # INITIAL INPUT STATE
    initial_state: AutoSecState = {
        "project_name": SELECTED_PROJECT.project_name,
        "vuln_id": SELECTED_PROJECT.cwe_id,
        "language": "java",
        "finder_model": "qwen2.5-32b",
        "finder_reanalyze": False,
    }

    workflow = _build_workflow()

    # Execute the graph
    final_state = workflow.invoke(initial_state)

    print("\n====== STATE DUMP ======")
    print(final_state)
    print("======^==========^======\n")
    print(json.dumps(final_state, indent=2))
    print("======^==========^======\n")


# standalone execution
if __name__ == "__main__":
    pipeline_main()