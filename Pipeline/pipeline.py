# Pipeline/pipeline.py
import argparse
import json
import subprocess
import os
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from . import logger
from .project_variants import ProjectVariants
from .utils import (
    has_actionable_vulnerabilities,
    load_dummy_finder_output,
    load_dummy_patcher_output,
    parse_exploiter_report,
    save_state_dump,
    save_state_dump,
    load_dummy_finder_output,
    load_dummy_patcher_output,
    has_actionable_vulnerabilities,
    parse_exploiter_report
)

from Agents.Finder.src.output_converter import sarif_to_finder_output
from Agents.Finder.src.types import FinderOutput
from Agents.Patcher import patcher_main
from Agents.Verifier import verifier_main


# Relative path information
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = (BASE_DIR / "Projects").resolve()
AGENTS_DIR = (BASE_DIR / "Agents").resolve()

MAX_EXPLOITER_RETRIES = 1
DEFAULT_PROJECT_VARIANT = ProjectVariants.WHITESOURCE_CUREKIT_CVE_2022_23082.name


class PipelineMode(str, Enum):
    ALL = "all"
    FINDER = "finder"
    EXPLOITER = "exploiter"
    PATCHER = "patcher"
    VERIFIER = "verifier"


class AutoSecState(TypedDict, total=False):
    project_name: Optional[str]
    language: Optional[str]
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    finder_model: Optional[str]
    finder_reanalyze: Optional[bool]
    finder_output: Optional[FinderOutput]
    artifacts: Optional[Dict[str, str]]
    exploiter: Optional[Dict[str, Any]]
    exploiter_retries: Optional[int]
    patcher: Optional[Dict[str, Any]]
    verifier: Optional[Dict[str, Any]]
    pipeline_mode: Optional[str]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AutoSec LangGraph pipeline."
    )

    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT_VARIANT,
        help=(
            "ProjectVariants enum name or project slug. "
            f"Defaults to {DEFAULT_PROJECT_VARIANT}."
        ),
    )

    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in PipelineMode],
        default=PipelineMode.ALL.value,
        help="Pipeline mode to run. Defaults to all.",
    )

    parser.add_argument(
        "--finder-model",
        default="gpt-5-mini",
        help="Finder model to use. Defaults to gpt-5-mini.",
    )

    parser.add_argument(
        "--language",
        default="java",
        help="Project language. Defaults to java.",
    )

    parser.add_argument(
        "--finder-reanalyze",
        action="store_true",
        default=False,
        help=(
            "Reuse the existing project source tree (skip re-extraction from zip) "
            "and bypass any cached/dummy Finder output, forcing IRIS to recompute. "
            "Defaults to false (re-extract source from zip on each run)."
        ),
    )

    parser.add_argument(
        "--use-dummy",
        action="extend",
        nargs="*",
        choices=["finder", "exploiter", "patcher"],
        default=["finder"],
        help=(
            "Add to the default dummy set [finder]. "
            "Examples: '--use-dummy patcher' -> [finder, patcher]; "
            "'--use-dummy finder exploiter' -> [finder, exploiter]."
        ),
    )

    return parser.parse_args()


def _resolve_project_variant(project_arg: str) -> ProjectVariants:
    """
    Resolve a project from either:
    1. ProjectVariants enum name:
       XWIKI_XWIKI_COMMONS_CVE_2023_29528

    2. Actual project slug:
       xwiki__xwiki-commons_CVE-2023-29528_14.9-rc-1
    """
    normalized_arg = project_arg.strip()

    # 1. Exact enum name match
    try:
        return ProjectVariants[normalized_arg]
    except KeyError:
        pass

    # 2. Case-insensitive enum name match
    upper_arg = normalized_arg.upper()
    for enum_name, variant in ProjectVariants.__members__.items():
        if enum_name.upper() == upper_arg:
            return variant

    # 3. Exact project slug match using ProjectVariants helper
    try:
        return ProjectVariants.from_project_slug(normalized_arg)
    except ValueError:
        pass

    valid_options = "\n".join(
        f"{variant.name} -> {variant.project_name}"
        for variant in ProjectVariants
    )

    raise ValueError(
        f"Unknown project: {normalized_arg}\n\n"
        f"You can pass either the enum name or the project slug.\n\n"
        f"Valid options are:\n{valid_options}"
    )


def _build_initial_state(
    selected_project: ProjectVariants,
    args: argparse.Namespace,
) -> AutoSecState:
    initial_state: AutoSecState = {
        "project_name": selected_project.project_name,
        "vuln_id": selected_project.cwe_id,
        "language": args.language,
        "finder_model": args.finder_model,
        "finder_reanalyze": args.finder_reanalyze,
        "pipeline_mode": args.mode,
    }

    dummy_set = set(args.use_dummy)

    if "finder" in dummy_set:
        initial_state["finder_output"] = load_dummy_finder_output(
            selected_project.dummy_finder_output
        )

    if "exploiter" in dummy_set:
        initial_state["exploiter"] = {
            "success": True,
            "report_path": None,
            "pov_test_paths": [],
            "pov_logic": selected_project.dummy_exploiter_pov_logic,
            "from_cache": False,
            "dummy": True,
        }

    if "patcher" in dummy_set:
        initial_state["patcher"] = {
            "success": True,
            "artifact_path": load_dummy_patcher_output(
                AGENTS_DIR,
                selected_project,
            ),
            "dummy": True,
        }

    return initial_state


def _build_workflow(mode: PipelineMode) -> Any:
    graph = StateGraph(AutoSecState)
    graph.add_node("finder", _finder_node)
    graph.add_node("exploiter", _exploiter_node)
    graph.add_node("patcher", _patcher_node)
    graph.add_node("verifier", _verifier_node)

    if mode == PipelineMode.ALL:
        graph.add_edge(START, "finder")
        graph.add_edge("finder", "exploiter")
        # exploiter -> patcher is handled dynamically by Command(...)
        graph.add_edge("patcher", "verifier")
        graph.add_edge("verifier", END)

    elif mode == PipelineMode.FINDER:
        graph.add_edge(START, "finder")
        graph.add_edge("finder", END)

    elif mode == PipelineMode.EXPLOITER:
        graph.add_edge(START, "exploiter")
        # exploiter exits to END through next_after_exploiter(...)

    elif mode == PipelineMode.PATCHER:
        graph.add_edge(START, "patcher")
        graph.add_edge("patcher", END)

    elif mode == PipelineMode.VERIFIER:
        graph.add_edge(START, "verifier")
        graph.add_edge("verifier", END)

    else:
        raise ValueError(f"Unsupported pipeline mode: {mode}")

    return graph.compile()


def _route_after_exploiter(state: AutoSecState) -> str:
    """
    Route after exploiter.

    In full pipeline mode, continue to patcher.
    In exploiter-only mode, stop after exploiter.
    """
    if state.get("pipeline_mode") == PipelineMode.EXPLOITER.value:
        return END

    return "patcher"

#* =============== Primary Agent Nodes =============== *#

def _finder_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - finder started")

    # Skip finder if output was already injected, e.g. dummy/cached output.
    # finder_reanalyze=True overrides the cache to force a real run.
    if state.get("finder_output") is not None and not state.get("finder_reanalyze"):
        logger.info("Node - finder skipped because finder_output is already set")
        return state

    # make sure Project/Sources folder exists
    Path(PROJECTS_DIR / "Sources").mkdir(exist_ok=True)

    host_ws = os.environ.get("HOST_WORKSPACE")
    if not host_ws:
        raise RuntimeError("HOST_WORKSPACE env var not set. Add it in devcontainer.json.")
    host_ws = host_ws.replace("\\", "/") # for windows compatibility

    host_ws = host_ws.replace("\\", "/")

    project_name = state["project_name"]
    vuln_id = state["vuln_id"]
    model = state["finder_model"]

    if not project_name:
        raise ValueError("project_name missing from state")

    if not vuln_id:
        raise ValueError("vuln_id missing from state")

    if not model:
        raise ValueError("finder_model missing from state")

    query = vuln_id + "wLLM"

    build_and_analyze_args = (
        f"--project-name {project_name} "
        f"--query {query} "
        f"--model {model} "
        f"--overwrite "
    )

    # finder_reanalyze=True keeps the existing source tree (e.g. Exploiter retry
    # where the project is already extracted). Default re-extracts from the zip.
    # Fallback: if the source tree isn't actually on disk (e.g. dummy was used
    # on the first pass so IRIS never extracted), force re-extraction even when
    # finder_reanalyze=True — otherwise IRIS's Maven build would have nothing
    # to compile against.
    project_source_dir = PROJECTS_DIR / "Sources" / project_name
    keep_source = state.get("finder_reanalyze", False) and project_source_dir.exists()

    if not keep_source:
        if state.get("finder_reanalyze") and not project_source_dir.exists():
            logger.info(
                f"finder_reanalyze=True but source tree missing at "
                f"{project_source_dir}; forcing re-extraction from zip."
            )
        build_and_analyze_args += f"--zip-path /workspace/Projects/Zipped/{project_name}.zip"

    print(f"\n---- ARGS: {build_and_analyze_args} ----\n")

    if model.startswith("gpt"):
        os.getenv("OPEN_AI_KEY")
    elif model.startswith("gemini"):
        os.getenv("GOOGLE_API_KEY")

    # 1. setup command to have IRIS inside docker container
    docker_cmd = [
        "docker",
        "run",
        "--platform=linux/amd64",
        "--rm",
        "-e",
        "OPENAI_API_KEY",
        "-e",
        "GOOGLE_API_KEY",
        "-v",
        f"{host_ws}/Projects:/workspace/Projects",
        "-v",
        f"{host_ws}/Agents:/workspace/Agents",
        "-w",
        "/workspace/Agents/Finder",
        "iris:latest",
        "bash",
        "-lc",
        "source /opt/conda/etc/profile.d/conda.sh && conda activate iris && "
        "python3 ./scripts/build_and_analyze.py " + build_and_analyze_args,
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

    sarif_path = (
        f"./Agents/Finder/output/{project_name}/test/"
        f"{query}-posthoc-filter/results.sarif"
    )

    try:
        with open(sarif_path) as f:
            findings = json.load(f)

        state["finder_output"] = sarif_to_finder_output(
            findings,
            cwe_id=vuln_id,
        )
        state["vuln"] = findings

    except FileNotFoundError:
        print("Finder found no vulnerabilities")
        state["finder_output"] = None
        state["vuln"] = None

    state["finder_reanalyze"] = False
    return state


def _exploiter_node(state: AutoSecState) -> Command:
    logger.info("Node: exploiter started")
    RUNNING_FINDER = True

    # Skip if dummy exploiter data was injected via --use-dummy exploiter.
    # The "dummy" flag is set in _build_initial_state.
    existing_exploiter = state.get("exploiter") or {}
    if existing_exploiter.get("dummy"):
        logger.info("Node: exploiter skipped (dummy data injected)")
        return Command(goto=_route_after_exploiter(state), update=state)

    running_finder = True

    new_state: AutoSecState = dict(state)
    project_name = new_state.get("project_name")

    if not project_name:
        raise ValueError("project_name missing from state")

    finder_output = new_state.get("finder_output")

    if not has_actionable_vulnerabilities(finder_output):
        logger.info("Node: exploiter found no actionable vulnerabilities. Execution ends.")

        vulnerabilities = []
        if finder_output:
            vulnerabilities = finder_output.get("vulnerabilities", [])

        reason = (
            "No vulnerabilities found in finder output."
            if not vulnerabilities
            else "Vulnerabilities were present, but none had traces for exploitation."
        )

        new_state["exploiter"] = {
            "success": False,
            "report_path": None,
            "pov_test_paths": None,
            "pov_logic": None,
            "from_cache": False,
            "skipped": True,
            "reason": reason,
        }

        new_state["patcher"] = {
            "success": False,
            "artifact_path": None,
            "skipped": True,
            "reason": reason,
        }

        new_state["verifier"] = {
            "success": False,
            "output_dir": None,
            "skipped": True,
            "reason": reason,
        }

        return Command(goto=END, update=new_state)

    # setup paths for exploiter
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
        "result.json",
    )

    fetch_one_location = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "scripts",
        "fetch_one.py",
    )

    generate_dockerfiles_location = os.path.join(
        exploiter_dir,
        "scripts",
        "generate_dockerfiles.py",
    )

    project_directory = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "project-sources",
        project_name,
    )

    working_directory = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "workdir_no_branch",
        "project-sources",
        project_name,
    )

    dockerfiles = os.path.join(
        exploiter_dir,
        "data",
        "cwe-bench-java",
        "Dockerfiles",
    )

    # Cache check
    if os.path.exists(report_path):
        logger.info(
            f"Cache hit: exploiter report found at {report_path}, "
            "skipping exploitation."
        )

        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)

        exploitable, pov_test_paths, pov_logic = parse_exploiter_report(report_data)

        new_state["exploiter"] = {
            "success": exploitable,
            "report_path": report_path,
            "pov_test_paths": pov_test_paths,
            "pov_logic": pov_logic,
            "from_cache": True,
        }

        if not exploitable:
            logger.warning(
                "Cached report shows vulnerability was not exploitable."
            )
            return Command(goto=_route_after_exploiter(new_state), update=new_state)

        logger.info("Cached report shows vulnerability exploited.")
        return Command(goto=_route_after_exploiter(new_state), update=new_state)

    exploiter_main = os.path.join(exploiter_dir, "main.py")

    if not os.path.exists(exploiter_main):
        raise FileNotFoundError(f"Exploiter entrypoint not found: {exploiter_main}")

    if os.path.exists(working_directory):
        shutil.rmtree(working_directory)

    if running_finder:
        try:
            Path(finder_output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(finder_output_path, "w", encoding="utf-8") as file:
                json.dump(new_state["finder_output"], file, indent=2)

        except FileNotFoundError:
            logger.error(f"Exploiter finder output file not found: {finder_output_path}")
            new_state["exploiter"] = {
                "success": False,
                "report_path": None,
                "pov_test_paths": None,
                "pov_logic": None,
                "from_cache": False,
            }
            return Command(goto=_route_after_exploiter(new_state), update=new_state)

    # prepare the project in the Exploiter's directory
    # check if they exist they do no need to fetch it anymore
    if not os.path.exists(project_directory):
        try:
            subprocess.run(
                [sys.executable, fetch_one_location, project_name],
                check=True,
            )

        except subprocess.CalledProcessError as e:
            logger.error(f"Exploiter subprocess failed during fetch_one.py exit={e.returncode}.")
            new_state["exploiter"] = {
                "success": False,
                "report_path": None,
                "pov_test_paths": None,
                "pov_logic": None,
                "from_cache": False,
            }
            return Command(goto=_route_after_exploiter(new_state), update=new_state)

    dockerfile_src = os.path.join(dockerfiles, project_name, "Dockerfile.vuln")

    # Generate (or regenerate) the Dockerfile if it is missing or still uses the
    # old single-test format (CWE_ID_*.java discovery instead of AutoSecFlow*Test).
    def _dockerfile_needs_generation(path: str) -> bool:
        if not os.path.exists(path):
            return True
        try:
            with open(path, encoding="utf-8") as _f:
                return "AutoSecFlow" not in _f.read()
        except OSError:
            return True

    if _dockerfile_needs_generation(dockerfile_src):
        vuln_id = new_state.get("vuln_id", "")
        logger.info(
            f"Generating Dockerfile for {project_name} (cwe={vuln_id}) "
            f"at {dockerfile_src}"
        )
        try:
            subprocess.run(
                [
                    sys.executable,
                    generate_dockerfiles_location,
                    "--project", project_name,
                    "--cwe", vuln_id,
                    "--force",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(
                f"Dockerfile generation failed for {project_name} "
                f"(exit={e.returncode}). Pipeline cannot continue."
            )
            new_state["exploiter"] = {
                "success": False,
                "report_path": None,
                "pov_test_paths": None,
                "pov_logic": None,
                "from_cache": False,
            }
            return Command(goto=_route_after_exploiter(new_state), update=new_state)

    logger.info(
        f"Copying dockerfile {dockerfile_src} into project path: {project_directory}"
    )
    shutil.copy2(dockerfile_src, project_directory)

    EXPLOITER_TIMEOUT = 2700

    run_cmd = [
        sys.executable,
        "main.py",
        "--dataset",
        "cwe-bench-java",
        "--project",
        project_name,
        "--model",
        "gpt5",
        "--budget",
        "5.0",
        "--timeout",
        str(EXPLOITER_TIMEOUT),
        "--no_branch",
        "--verbose",
    ]

    # STARTING EXPLOITATION
    try:
        logger.info(f"Loading project: {project_name}")
        logger.info(f"Running command: {run_cmd}")
        subprocess.run(
            run_cmd,
            cwd=exploiter_dir,
            check=True,
            timeout=EXPLOITER_TIMEOUT + 60,
        )

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
        logger.error(f"Exploiter subprocess failed exit={e.returncode}.")
        new_state["exploiter"] = {
            "success": False,
            "report_path": None,
            "pov_test_paths": None,
            "pov_logic": None,
            "from_cache": False,
        }
        return Command(goto=_route_after_exploiter(new_state), update=new_state)

        return Command(goto="patcher", update=new_state)

    # checking if result produced properly
    if not os.path.exists(report_path):
        logger.error(f"Exploiter report not found: {report_path}")
        new_state["exploiter"] = {
            "success": False,
            "report_path": None,
            "pov_test_paths": None,
            "pov_logic": None,
            "from_cache": False,
        }
        return Command(goto=_route_after_exploiter(new_state), update=new_state)

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    exploitable, pov_test_paths, pov_logic = parse_exploiter_report(report_data)

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
            logger.warning(
                f"Exploiter did not find an exploitable PoV after "
                f"{retries} attempt(s)."
            )
            return Command(goto=_route_after_exploiter(new_state), update=new_state)

        logger.warning(
            f"Exploiter did not find an exploitable PoV "
            f"(attempt {retries}/{MAX_EXPLOITER_RETRIES}); re-running finder."
        )
        new_state["finder_reanalyze"] = True
        return Command(goto="finder", update=new_state)

    logger.info("Vulnerability exploited. Continuing to next pipeline stage.")
    return Command(goto=_route_after_exploiter(new_state), update=new_state)


def _patcher_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node - patcher started")

    if not state.get("language"):
        raise ValueError("language missing from state")

    if not state.get("project_name"):
        raise ValueError("project_name missing from state")

    if not state.get("finder_output"):
        raise ValueError("finder_output missing from state")

    pov_logic = "no pov_logic provided"

    exploiter_state = state.get("exploiter") or {}
    if exploiter_state.get("pov_logic"):
        pov_logic = exploiter_state["pov_logic"]
    else:
        logger.warning("pov_logic missing from exploiter output")

    # copy PoV tests from Exploiter's working dir into Projects/Sources
    project_name = state["project_name"]
    pov_test_paths = (state.get("exploiter") or {}).get("pov_test_paths") or []
    exploiter_project_root = (
        AGENTS_DIR
        / "Exploiter"
        / "data"
        / "cwe-bench-java"
        / "workdir_no_branch"
        / "project-sources"
        / project_name
    )

    sources_project_root = PROJECTS_DIR / "Sources" / project_name

    for rel_path in pov_test_paths:
        src = exploiter_project_root / rel_path
        dst = sources_project_root / rel_path

        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            logger.info(
                f"Copied PoV test: {rel_path} "
                f"→ Projects/Sources/{project_name}/{rel_path}"
            )
        else:
            logger.warning(f"PoV test file not found in exploiter workdir: {src}")

    finder_output = state["finder_output"]

    success, run_dir = patcher_main(
        language=state["language"],
        cwe_id=finder_output["cwe_id"],
        vulnerability_list=finder_output["vulnerabilities"],
        project_name=project_name,
        pov_logic=pov_logic,
        save_prompt=True,
    )

    state["patcher"] = {
        "success": success,
        "artifact_path": run_dir,
    }

    return state


def _verifier_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: verifier started")

    patcher_state = state.get("patcher", {})
    patcher_artifact_path = patcher_state.get("artifact_path", "")
    project_name = state.get("project_name", "")

    if not patcher_artifact_path:
        logger.error("No patcher artifact_path in state — skipping verifier")
        state["verifier"] = {
            "success": False,
            "error": "No patcher output",
        }
        return state

    run_dir = Path(patcher_artifact_path)
    manifest_files = sorted(run_dir.glob("patcher_manifest_*.json"))

    if not manifest_files:
        logger.error(f"No patcher manifest found in {run_dir}")
        state["verifier"] = {
            "success": False,
            "error": f"No manifest in {run_dir}",
        }
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


def pipeline_main() -> None:
    load_dotenv()

    args = _parse_args()
    mode = PipelineMode(args.mode)

    selected_project = _resolve_project_variant(args.project)
    initial_state = _build_initial_state(selected_project, args)

    logger.info(
        f"Starting pipeline with "
        f"mode={mode.value}, "
        f"project={selected_project.project_name}, "
        f"use_dummy={args.use_dummy}, "
        f"finder_reanalyze={args.finder_reanalyze}"
    )

    workflow = _build_workflow(mode)
    final_state = workflow.invoke(initial_state)

    # Save to file
    file_path = save_state_dump(final_state)
    if file_path:
        print(f"[Pipeline] State dump saved to: {file_path}")


# standalone execution
if __name__ == "__main__":
    pipeline_main()