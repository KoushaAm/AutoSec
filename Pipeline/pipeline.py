from typing import TypedDict, Dict, Any, Optional
import logging
import uuid
import argparse
import json
import subprocess
import pathlib
from langgraph.graph import StateGraph, END, START

# Import our verifier
from verifier import create_verifier

# Minimal logging
logging.basicConfig(level=logging.ERROR)

class AutoSecState(TypedDict, total=False):
    vuln_id: Optional[str]
    vuln: Optional[Dict[str, Any]]
    artifacts: Optional[Dict[str, str]]
    exploiter: Optional[Dict[str, Any]]
    patcher: Optional[Dict[str, Any]]
    verifier: Optional[Dict[str, Any]]  

    # workflow specific  
    fixer_output_path: Optional[str]
    verification_results: Optional[Dict[str, Any]]
    session_id: Optional[str]

def build_workflow() -> Any:
    graph = StateGraph(AutoSecState)
    graph.add_node("patcher", patcher_node)
    graph.add_node("verifier", verifier_node)
    graph.add_edge(START, "patcher")
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
    logger.info("Node: finder started")
    # implementation
    return state

def exploiter_node(state: AutoSecState) -> AutoSecState:
    logger.info("Node: exploiter started")  
    # TODO: Implement when Exploiter integration is ready
    return state

def patcher_node(state: AutoSecState) -> AutoSecState:
    session_id = str(uuid.uuid4())[:8]
    state["session_id"] = session_id
    
    try:
        fixer_path = pathlib.Path(__file__).parent.parent / "Experiments" / "Fixer"
        
        result = subprocess.run(
            ["python3", "fixer.py"],
            cwd=str(fixer_path),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            state["patcher"] = {"status": "failed", "error": result.stderr}
            return state
        
        output_dir = fixer_path / "output"
        output_files = list(output_dir.glob("*.json"))
        
        if not output_files:
            state["patcher"] = {"status": "failed", "error": "No output files"}
            return state
        
        latest_file = max(output_files, key=lambda f: f.stat().st_mtime)
        
        with open(latest_file, 'r') as f:
            fixer_output = json.load(f)
        
        patch_count = len(fixer_output.get("patches", []))
        print(f"Fixer: {latest_file.name} ({patch_count} patches)")
        
        state["fixer_output_path"] = str(latest_file)
        state["patcher"] = {"status": "success", "output_file": str(latest_file), "patch_count": patch_count}
        
        return state
        
    except Exception as e:
        state["patcher"] = {"status": "failed", "error": str(e)}
        return state

def verifier_node(state: AutoSecState) -> AutoSecState:
    if not state.get("fixer_output_path"):
        state["verifier"] = {"status": "failed", "error": "No input"}
        return state
    
    fixer_output_path = state["fixer_output_path"]
    
    try:
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        config = {"output_directory": "verifier/verifier_output"}
        verifier = create_verifier(config)
        verification_results = verifier.verify_fixer_output(fixer_output_path)
        
        sys.stdout = old_stdout
        
        safe_patches = len([r for r in verification_results if r.status.value == "patch_valid"])
        total_patches = len(verification_results)
        
        print(f"Verifier: {safe_patches}/{total_patches} patches safe")
        
        for r in verification_results:
            cwe_id = r.patcher_feedback.get('cwe_matches', [{}])[0].get('cwe_id', 'Unknown')
            decision = "SAFE" if r.status.value == "patch_valid" else "VULNERABLE"
            print(f"  Patch {r.patch_id} ({cwe_id}): {decision}")
        
        results_summary = {
            "total_patches": total_patches,
            "safe_patches": safe_patches,
            "patches": [
                {
                    "patch_id": r.patch_id,
                    "status": r.status.value,
                    "decision": "SAFE" if r.status.value == "patch_valid" else "VULNERABLE",
                    "cwe_id": r.patcher_feedback.get('cwe_matches', [{}])[0].get('cwe_id', 'Unknown')
                }
                for r in verification_results
            ]
        }
        
        state["verifier"] = {"status": "success", "results_summary": results_summary}
        return state
        
    except Exception as e:
        state["verifier"] = {"status": "failed", "error": str(e)}
        return state

def main():
    parser = argparse.ArgumentParser(description="AutoSec Pipeline")
    args = parser.parse_args()
    
    workflow = build_workflow()
    initial_state = AutoSecState()
    
    try:
        final_state = workflow.invoke(initial_state)
        
        # output
        print("\nFiles created:")
        
        # fixer output
        fixer_output_dir = pathlib.Path("../Experiments/Fixer/output")
        if fixer_output_dir.exists():
            fixer_files = list(fixer_output_dir.glob("*.json"))
            if fixer_files:
                latest_fixer = max(fixer_files, key=lambda f: f.stat().st_mtime)
                print(f"  {latest_fixer}")
        
        # verifier output
        verifier_output_dir = pathlib.Path("verifier/verifier_output")
        if verifier_output_dir.exists():
            sessions = list(verifier_output_dir.glob("session_*"))
            if sessions:
                latest_session = max(sessions, key=lambda f: f.stat().st_mtime)
                print(f"  {latest_session}/")
                
                patches = list(latest_session.glob("patch_*"))
                for patch_dir in sorted(patches):
                    print(f"    {patch_dir.name}/")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())