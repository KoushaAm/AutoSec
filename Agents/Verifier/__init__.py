"""
Verifier Agent Entry Point
"""

from pathlib import Path
from typing import Tuple, Optional
from .core.engine import create_verifier


def verifier_main(
    *,
    patcher_manifest_path: str,
    project_name: str,
    exploiter_pov_test_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Main entry point for Verifier called by Pipeline.
    
    Uses the existing VerifierCore engine to verify patches.
    
    Args:
        patcher_manifest_path: Path to Patcher's manifest JSON (patcher_*.json)
        project_name: Project name (e.g., "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5")
        exploiter_pov_test_path: path to Exploiter's POV test file
    
    Returns:
        (success: bool, output_dir: str)
    """
    
    print(f"\n{'='*80}")
    print(f"VERIFIER")
    print(f"{'='*80}")
    print(f"Project: {project_name}")
    print(f"Patcher manifest: {patcher_manifest_path}")
    if exploiter_pov_test_path:
        print(f"POV tests: {exploiter_pov_test_path}")
    print(f"{'='*80}\n")
    
    # Create verifier instance using existing engine
    verifier = create_verifier()
    
    # Run verification using existing verify_fixer_output method
    results = verifier.verify_fixer_output(patcher_manifest_path)
    
    # Determine success
    if not results:
        print("\n⚠️  No patches were verified (Patcher output may be empty)")
        success = False
    else:
        passed = sum(1 for r in results if r.status.value == "PASS")
        failed = len(results) - passed
        
        print(f"\n{'='*80}")
        print("VERIFICATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total patches: {len(results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"{'='*80}\n")
        
        success = (failed == 0)
    
    # Get output directory from artifact manager
    output_dir = verifier.artifact_manager.base_output_dir
    
    print(f"📂 Verification results saved to: {output_dir}")
    
    return success, str(output_dir)


__all__ = ["verifier_main"]
