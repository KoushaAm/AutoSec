import shutil
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
from datetime import datetime
from dotenv import load_dotenv

# from Agents.Exploiter.data.primevul.setup import project_slug
# local imports
from . import logger
from .utils import load_dummy_finder_output, load_dummy_patcher_output, save_state_dump
from .project_variants import ProjectVariants

from Agents.Patcher import patcher_main
from Agents.Verifier import verifier_main
from Agents.Finder.src.types import FinderOutput
from Agents.Finder.src.output_converter import sarif_to_finder_output
from datetime import datetime

# relative path information
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = (BASE_DIR / "Projects").resolve()
AGENTS_DIR   = (BASE_DIR / "Agents").resolve()

MAX_EXPLOITER_RETRIES = 1

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
    exploiter_retries: Optional[int]    # tracks finder→exploiter retry cycles
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
    graph.add_edge("exploiter", "patcher")
    graph.add_edge("patcher", "verifier")
    graph.add_edge("verifier", END)

    # conditional edges
    # exploiter -> finder OR exploiter -> patcher
    # verifier -> finder OR verifier -> end

    workflow = graph.compile()
    return workflow


def _finder_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - finder started")

    # Skip finder if output was already injected (e.g. dummy/cached output)
    if state.get("finder_output") is not None:
        logger.info("Node - finder skipped (finder_output already set)")
        return state

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

    if model.startswith("gpt"):
        os.getenv("OPEN_AI_KEY")
    elif model.startswith("gemini"):
        os.getenv("GOOGLE_API_KEY")

    # 1. setup command to have IRIS inside docker container
    docker_cmd = [
        "docker", "run",
        "--platform=linux/amd64",
        "--rm",
        "-e", "OPENAI_API_KEY",
        "-e", "GOOGLE_API_KEY",
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


def _parse_exploiter_report(report_data) -> tuple[bool, list[str], str]:
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




def _exploiter_node(state: AutoSecState) -> Command:
    logger.info("Node: exploiter started")
    RUNNING_FINDER = True

    # Taking a copy of the state
    new_state = dict(state)
    project_name = new_state.get("project_name")
    if not project_name:
        raise ValueError("project_name missing from state")

    # Check if any vulnerability was found: if it wasn't we go to the end of the pipeline no need to continue
    vuln = new_state["finder_output"]["vulnerabilities"]
    found = False
    if len(vuln) > 0:
        found = True

    if not found:
        logger.info(f"Node: exploiter found no vulnerabilities. Execution ends.")
        return Command(goto=END, update=new_state)


    exploiter_dir = os.path.join(os.getcwd(), "Agents", "Exploiter")

    report_path = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "workdir_no_branch",
        "project-sources",
        project_name,
        "report.json",
    )

    finder_output_path = os.path.join(
        exploiter_dir,
        "vuln_agent",
        "modules",
        "data",
        "traces",
        "result.json"
    )

    fetch_one_location = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "scripts",
        "fetch_one.py"
    )

    project_directory = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "project-sources",
        project_name
    )

    working_directory = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "workdir_no_branch",
        "project-sources",
        project_name
    )

    dockerfiles = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "Dockerfiles",
    )

    # CACHE CHECK
    # If a report.json already exists from a previous run, skip re-running the
    if os.path.exists(report_path):
        logger.info(f"Cache hit: exploiter report found at {report_path}, skipping exploitation.")
        with open(report_path, "r") as f:
            report_data = json.load(f)

        exploitable, pov_test_paths, pov_logic = _parse_exploiter_report(report_data)

        new_state["exploiter"] = {
            "success": exploitable,
            "report_path": report_path,
            "pov_test_paths": pov_test_paths,
            "pov_logic": pov_logic,
            "from_cache": True,
        }

        if not exploitable:
            logger.warning("Cached report shows vulnerability was not exploitable — ending pipeline.")
            return Command(goto="patcher", update=new_state)

        logger.info("Cached report shows vulnerability exploited! Continuing to patcher.")
        return Command(goto="patcher", update=new_state)

    exploiter_main = os.path.join(exploiter_dir, "main.py")

    if not os.path.exists(exploiter_main):
        raise FileNotFoundError(f"Exploiter entrypoint not found: {exploiter_main}")

    # if directory exists but report.json (meaning the output) isn't present we delete the project
    # and start again
    if os.path.exists(working_directory):
        shutil.rmtree(working_directory)

    # ####  ENVIRONMENT SETUP FOR CWE-BENCH PROJECT ####

    # load finder output and save it to the directory exploiter uses
    if RUNNING_FINDER:
        try :
            with open(finder_output_path, "w") as file:
                json.dump(new_state["finder_output"], file)
        except FileNotFoundError:
            logger.error(f"Exploiter finder output file not found: {finder_output_path}")
            new_state["exploiter"] = {
                "success": False,
                "report_path": None,
                "pov_test_paths": None,
                "pov_logic": None,
                "from_cache": False,
            }
            return Command(goto="patcher", update=new_state)

    # prepare the project in the Exploiter's directory
    # check if they exist they do no need to fetch it anymore
    if not os.path.exists(project_directory):
        try:
            subprocess.run([sys.executable, fetch_one_location, project_name], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Exploiter subprocess failed (exit={e.returncode}).")
            new_state["exploiter"] = {
                "success": False,
                "report_path": None,
                "pov_test_paths": None,
                "pov_logic": None,
                "from_cache": False,
            }
            return Command(goto="patcher", update=new_state)

    # copy over the dockerfile from dockerfiles directory (always, in case it changed)
    logger.info(f"copying docker {os.path.join(dockerfiles, project_name, 'Dockerfile.vuln')} into project path: {project_directory}" )
    shutil.copy2(os.path.join(dockerfiles, project_name, "Dockerfile.vuln"), project_directory)

    # Execution
    EXPLOITER_TIMEOUT = 2700

    run_cmd = [
        sys.executable,
        "main.py",
        "--dataset", "cwe-bench-java",
        "--project", project_name,
        "--model", "gpt5",
        "--budget", "5.0",
        "--timeout", str(EXPLOITER_TIMEOUT),
        "--no_branch",
        "--verbose",
    ]

    # STARTING EXPLOITATION
    try:
        logger.info("Loading the project: " + project_name)
        logger.info(f"Running command: {run_cmd}")
        subprocess.run(run_cmd, cwd=exploiter_dir, check=True, timeout=EXPLOITER_TIMEOUT + 60)
    except subprocess.TimeoutExpired:
        logger.error(f"Exploiter timed out after {EXPLOITER_TIMEOUT + 60}s.")
        new_state["exploiter"] = {
            "success": False,
            "report_path": None,
            "pov_test_paths": None,
            "pov_logic": None,
            "from_cache": False,
        }
        return Command(goto="patcher", update=new_state)

    except subprocess.CalledProcessError as e:
        logger.error(f"Exploiter subprocess failed (exit={e.returncode}).")
        new_state["exploiter"] = {
            "success": False,
            "report_path": None,
            "pov_test_paths": None,
            "pov_logic": None,
            "from_cache": False,
        }

        return Command(goto="patcher", update=new_state)

    # checking if result produced properly
    if not os.path.exists(report_path):
        logger.error(f"Exploiter report not found: {report_path}")

        return Command(goto="patcher", update=new_state)

    with open(report_path, "r") as f:
        report_data = json.load(f)

    exploitable, pov_test_paths, pov_logic = _parse_exploiter_report(report_data)

    new_state["exploiter"] = {
        "success": exploitable,
        "report_path": report_path,
        "pov_test_paths": pov_test_paths,
        "pov_logic": pov_logic,
        "from_cache": False,
    }

    if not exploitable:
        retries = new_state.get("exploiter_retries", 0) + 1
        new_state["exploiter_retries"] = retries
        if retries >= MAX_EXPLOITER_RETRIES:
            logger.warning(f"Exploiter did not find an exploitable PoV after {retries} attempt(s) — ending pipeline.")

            return Command(goto="patcher", update=new_state)
        logger.warning(f"Exploiter did not find an exploitable PoV (attempt {retries}/{MAX_EXPLOITER_RETRIES}), re-running finder.")
        new_state["finder_reanalyze"] = True
        return Command(goto="finder", update=new_state)

    logger.info("Vulnerability exploited! Continuing to patcher.")
    return Command(goto="patcher", update=new_state)



def _patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - patcher started")

    if not state.get("language"):
        raise ValueError("language missing from state")

    if not state.get("project_name"):
        raise ValueError("project_name missing from state")

    # TODO: currently using dummy finder_output
    if not state.get("finder_output"):
        raise ValueError("finder_output missing from state")

    # TODO: currently using dummy exploiter pov_logic
    if not state.get("exploiter"):
        raise ValueError("exploiter output missing from state")

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


def _verifier_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: verifier started")

    patcher_state = state.get("patcher", {})
    patcher_artifact_path = patcher_state.get("artifact_path", "")
    project_name = state.get("project_name", "")

    if not patcher_artifact_path:
        logger.error("No patcher artifact_path in state — skipping verifier")
        state["verifier"] = {"success": False, "error": "No patcher output"}
        return state

    run_dir = Path(patcher_artifact_path)
    manifest_files = sorted(run_dir.glob("patcher_manifest_*.json"))

    if not manifest_files:
        logger.error(f"No patcher manifest found in {run_dir}")
        state["verifier"] = {"success": False, "error": f"No manifest in {run_dir}"}
        return state

    manifest_path = str(manifest_files[0])
    logger.info(f"Using patcher manifest: {manifest_path}")

    success, output_dir = verifier_main(
        patcher_manifest_path=manifest_path,
        project_name=project_name,
    )

    state["verifier"] = {
        "success": success,
        "output_dir": output_dir,
    }

    return state


# ====== Execute workflow =====
def pipeline_main():
    load_dotenv()

    SELECTED_PROJECT = ProjectVariants.NAHSRA_2022_29577

    # INITIAL INPUT STATE
    initial_state: AutoSecState = {
        "project_name": SELECTED_PROJECT.project_name,
        "vuln_id": SELECTED_PROJECT.cwe_id,
        "language": "java",
        "finder_model": "gpt-5-mini",
        "finder_reanalyze": False,
        # Dummy inputs for development & experiments
        "finder_output": load_dummy_finder_output(SELECTED_PROJECT.dummy_finder_output),
        # "exploiter": {
        #     "pov_logic": SELECTED_PROJECT.dummy_exploiter_pov_logic
        # }
    }

    # print(json.dumps(initial_state, indent=2))

    # Execute the graph
    workflow = _build_workflow()
    final_state = workflow.invoke(initial_state)

    print("\n====== STATE DUMP ======")
    print(json.dumps(final_state, indent=2))
    print("======^==========^======\n")


# standalone execution
if __name__ == "__main__":
    pipeline_main()