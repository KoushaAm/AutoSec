"""
Verifier Agent Entry Point
"""

import pathlib
from typing import Dict, Any, Optional
from .core.engine import create_verifier
from .config import LATEST_PATCHER_OUTPUT


def verifier_main(input_path: Optional[str] = None, use_latest: bool = True) -> Dict[str, Any]:
    """
    Main entry point for the Verifier agent.
    
    Args:
        input_path: Path to Patcher output JSON file or directory
        use_latest: If True, use the latest Patcher output
    
    Returns:
        Dictionary with verification results summary
    """
    verifier = create_verifier()
    
    # Determine input file
    if use_latest or input_path is None:
        target_path = LATEST_PATCHER_OUTPUT
    else:
        target_path = pathlib.Path(input_path)
    
    # Find the JSON file
    if target_path.is_dir():
        json_files = list(target_path.glob("patch_*.json"))
        if not json_files:
            return {
                "success": False,
                "error": f"No patch_*.json files found in {target_path}",
                "patches_verified": 0
            }
        input_file = json_files[0]
    else:
        input_file = target_path
    
    if not input_file.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_file}",
            "patches_verified": 0
        }
    
    # Run verification
    print(f"Running Verifier on: {input_file}")
    results = verifier.verify_fixer_output(str(input_file))
    
    # Summarize results
    passed = sum(1 for r in results if r.status.value == "PASS")
    failed = sum(1 for r in results if r.status.value == "FAIL")
    
    summary = {
        "success": True,
        "patches_verified": len(results),
        "passed": passed,
        "failed": failed,
        "results": results
    }
    
    print(f"\n✅ Verification complete! {passed}/{len(results)} patch(es) passed")
    
    return summary


__all__ = ["verifier_main"]
