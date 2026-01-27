#!/usr/bin/env python3
import argparse
import json
import pathlib
import sys
import datetime
from typing import Dict, Any, List, Optional

# Import our components
from .core.engine import create_verifier
from .models.verification import VerificationStatus


class UnifiedVerifier:
    """
    Main verifier class that orchestrates the complete verification workflow.
    This will eventually be moved to Agents/ for the official pipeline.
    """
    
    def __init__(self, output_dir: str = "unified_verification_output"):
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the pipeline verifier (which now uses LLM patch application)
        self.verifier = create_verifier({"output_directory": str(self.output_dir)})
        
        print("Unified Verifier Initialized")
        print(f"Output directory: {self.output_dir}")
    
    def run_complete_verification(self, patcher_output_path: pathlib.Path) -> Dict[str, Any]:
        """
        Run the complete verification workflow on Patcher output.
        
        Args:
            patcher_output_path: Path to Patcher output directory or summary file
            
        Returns:
            Complete verification results with decisions
        """
        print("\n" + "="*60)
        print("VERIFIER - Patch Validation")
        print("="*60)
        
        # Step 1: Prepare input file
        input_file = self._prepare_input_file(patcher_output_path)
        if not input_file:
            return {"status": "error", "message": "Failed to prepare input file"}
        
        print(f"Input: {input_file.name}\n")
        
        try:
            verification_results = self.verifier.verify_fixer_output(str(input_file))
            
            # Step 3: POV Testing (placeholder)
            pov_results = self._run_pov_tests(verification_results)
            
            # Step 4: Regression Suite (placeholder for future)
            regression_results = self._run_regression_suite(verification_results)
            
            # Step 5: Generate final decisions
            final_results = self._generate_final_decisions(
                verification_results, pov_results, regression_results
            )
            
            # Step 6: Save complete results
            print("\n--- VERIFICATION COMPLETE ---")
            session_file = self._save_complete_results(final_results, input_file)
            
            # Step 7: Print summary
            self._print_final_summary(final_results)
            
            return {
                "status": "success",
                "results": final_results,
                "session_file": str(session_file)
            }
            
        except Exception as e:
            error_msg = f"Verification workflow failed: {str(e)}"
            print(f"\nERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            
            return {
                "status": "error",
                "message": error_msg,
                "traceback": traceback.format_exc()
            }
    
    def _prepare_input_file(self, patcher_path: pathlib.Path) -> Optional[pathlib.Path]:
        """Prepare input file for verification from Patcher output"""
        if patcher_path.is_file():
            # Already a file, use it directly
            return patcher_path
        
        if patcher_path.is_dir():
            # Directory - look for summary or create from individual patches
            summary_files = list(patcher_path.glob("*summary*.json"))
            if summary_files:
                return summary_files[0]
            
            # Create summary from individual patches
            patch_files = list(patcher_path.glob("patch_*.json"))
            if patch_files:
                return self._create_summary_from_patches(patcher_path, patch_files)
        
        print(f"ERROR: Invalid patcher output path: {patcher_path}")
        return None
    
    def _create_summary_from_patches(self, session_dir: pathlib.Path, patch_files: List[pathlib.Path]) -> pathlib.Path:
        """Create summary file from individual patch files"""
        print(f"Creating summary from {len(patch_files)} individual patch files...")
        
        patches = []
        for patch_file in sorted(patch_files):
            with open(patch_file, 'r') as f:
                patch_data = json.load(f)
            
            # Convert to pipeline_verifier format
            patches.append({
                "patch_id": patch_data["metadata"]["patch_id"],
                "unified_diff": patch_data["patch"]["unified_diff"],
                "touched_files": patch_data["patch"]["touched_files"],
                "cwe_matches": patch_data["patch"]["cwe_matches"],
                "plan": patch_data["patch"]["plan"],
                "confidence": patch_data["patch"]["confidence"],
                "verifier_confidence": patch_data["patch"]["confidence"],
                "risk_notes": patch_data["patch"]["risk_notes"],
                "assumptions": patch_data["patch"]["assumptions"],
                "behavior_change": patch_data["patch"]["behavior_change"],
                "safety_verification": patch_data["patch"]["safety_verification"]
            })
        
        # Save summary file
        summary_file = session_dir / "unified_verifier_summary.json"
        summary_data = {
            "patches": patches,
            "metadata": {
                "total_patches": len(patches),
                "created_by": "unified_verifier",
                "timestamp": datetime.datetime.now().isoformat()
            }
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        return summary_file
    
    def _run_pov_tests(self, verification_results: List[Any]) -> Dict[str, Any]:
        """Run POV tests (placeholder for future implementation)"""
        print("POV testing not yet implemented - placeholder results")
        
        # Placeholder - return mock results for now
        return {
            "pov_test_status": "not_implemented",
            "patches_tested": len(verification_results),
            "vulnerabilities_eliminated": "unknown",
            "note": "POV testing will be implemented in future version"
        }
    
    def _run_regression_suite(self, verification_results: List[Any]) -> Dict[str, Any]:
        """Run regression test suite (placeholder for future implementation)"""
        print("Regression suite not yet implemented - placeholder results")
        
        # Placeholder - return mock results for now
        return {
            "regression_status": "not_implemented",
            "patches_tested": len(verification_results),
            "regressions_detected": "unknown",
            "note": "Regression suite will be added shortly"
        }
    
    def _generate_final_decisions(self, verification_results: List[Any], 
                                 pov_results: Dict[str, Any], 
                                 regression_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate final verification decisions combining all test results"""
        final_results = []
        
        for result in verification_results:
            # Base decision from core verification
            base_decision = {
                "patch_id": result.patch_id,
                "core_verification": {
                    "status": result.status.value,
                    "reasoning": result.reasoning,
                    "build_success": result.build_success,
                    "test_success": result.test_success,
                    "verification_time": result.verification_time
                },
                "pov_testing": pov_results,
                "regression_testing": regression_results
            }
            
            # Determine final decision
            if result.status == VerificationStatus.PATCH_VALID:
                # For now, base final decision on core verification
                # TODO: Update when POV and regression tests are implemented
                base_decision["final_decision"] = "PATCH_VALIDATED"
                base_decision["confidence"] = "high"
                base_decision["reasoning"] = f"Core verification passed: {result.reasoning}"
            else:
                base_decision["final_decision"] = "PATCH_REJECTED"
                base_decision["confidence"] = "high" 
                base_decision["reasoning"] = f"Core verification failed: {result.reasoning}"
            
            # Add feedback for pipeline
            base_decision["pipeline_feedback"] = {
                "requires_revision": result.status != VerificationStatus.PATCH_VALID,
                "patcher_feedback": getattr(result, 'patcher_feedback', {}),
                "recommended_action": "accept" if result.status == VerificationStatus.PATCH_VALID else "revise"
            }
            
            final_results.append(base_decision)
        
        return final_results
    
    def _save_complete_results(self, final_results: List[Dict[str, Any]], 
                              input_file: pathlib.Path) -> pathlib.Path:
        """Save complete verification results"""
        timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
        session_name = f"unified_verification_{timestamp}"
        session_dir = self.output_dir / session_name
        session_dir.mkdir(exist_ok=True)
        
        # Save detailed results
        results_file = session_dir / "complete_results.json"
        complete_data = {
            "session_info": {
                "timestamp": datetime.datetime.now().isoformat(),
                "input_file": str(input_file),
                "session_dir": str(session_dir),
                "verifier_version": "unified-v1.0.0"
            },
            "verification_results": final_results,
            "summary": {
                "total_patches": len(final_results),
                "validated_patches": len([r for r in final_results if r["final_decision"] == "PATCH_VALIDATED"]),
                "rejected_patches": len([r for r in final_results if r["final_decision"] == "PATCH_REJECTED"])
            }
        }
        
        with open(results_file, 'w') as f:
            json.dump(complete_data, f, indent=2)
        
        print(f"Complete results saved to: {results_file}")
        return results_file
    
    def _print_final_summary(self, final_results: List[Dict[str, Any]]):
        """Print final verification summary"""
        print("\n" + "="*60)
        print("FINAL VERIFICATION SUMMARY")
        print("="*60)
        
        validated = 0
        rejected = 0
        
        for result in final_results:
            patch_id = result["patch_id"]
            decision = result["final_decision"]
            confidence = result["confidence"]
            reasoning = result["reasoning"]
            
            print(f"\nPatch {patch_id}: {decision} (confidence: {confidence})")
            print(f"  Reasoning: {reasoning}")
            
            if decision == "PATCH_VALIDATED":
                validated += 1
            else:
                rejected += 1
        
        total = len(final_results)
        success_rate = (validated / total * 100) if total > 0 else 0
        
        print(f"\n" + "-"*40)
        print(f"OVERALL RESULTS:")
        print(f"  Total patches: {total}")
        print(f"  Validated: {validated}")
        print(f"  Rejected: {rejected}")
        print(f"  Success rate: {success_rate:.1f}%")
        print("="*60)


def find_latest_patcher_output() -> Optional[pathlib.Path]:
    """Find the latest Patcher output directory"""
    patcher_output_dir = pathlib.Path("../Patcher/output")
    if not patcher_output_dir.exists():
        return None
    
    patcher_sessions = list(patcher_output_dir.glob("patcher_*"))
    if not patcher_sessions:
        return None
    
    return max(patcher_sessions, key=lambda p: p.name)


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Unified Verifier - Complete patch verification workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use latest Patcher output automatically
  python3 verifier.py --latest-patcher
  
  # Use specific Patcher output directory
  python3 verifier.py --input ../Patcher/output/patcher_20251127T221131Z
  
  # Use specific summary file
  python3 verifier.py --input /path/to/summary.json
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input", type=pathlib.Path,
                       help="Path to Patcher output directory or summary file")
    group.add_argument("--latest-patcher", action="store_true",
                       help="Use latest Patcher output automatically")
    
    parser.add_argument("--output-dir", default="unified_verification_output",
                       help="Output directory for results")
    
    args = parser.parse_args()
    
    # Determine input path
    if args.latest_patcher:
        input_path = find_latest_patcher_output()
        if not input_path:
            print("ERROR: No Patcher output found in ../Patcher/output/")
            sys.exit(1)
        print(f"Using latest Patcher output: {input_path.name}")
    else:
        input_path = args.input
        if not input_path.exists():
            print(f"ERROR: Input path does not exist: {input_path}")
            sys.exit(1)
    
    # Run unified verification
    verifier = UnifiedVerifier(args.output_dir)
    results = verifier.run_complete_verification(input_path)
    
    # Exit with appropriate code
    if results["status"] == "success":
        print(f"\nVerification completed successfully!")
        sys.exit(0)
    else:
        print(f"\nVerification failed: {results['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()