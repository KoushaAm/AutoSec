import subprocess
import pathlib
import sys
from typing import Dict, Any, Optional
from ..models.verification import VerificationResult, VerificationStatus, PatchInfo
import datetime

# Add existing Verifier infrastructure - fix path calculation
# Current file: pipeline_verifier/handlers/verification_handler.py
# Need to go up: handlers -> pipeline_verifier -> Verifier (3 levels, not 4)
VERIFIER_PATH = pathlib.Path(__file__).parent.parent.parent


class BuildVerifier:
    """Handles build verification and testing"""
    
    def __init__(self):
        self.verifier_path = VERIFIER_PATH
        self._ensure_verifier_path()
    
    def _ensure_verifier_path(self):
        """Ensure the verifier path is added to sys.path"""
        if str(self.verifier_path) not in sys.path:
            sys.path.insert(0, str(self.verifier_path))
    
    def run_verification(self, project_path: pathlib.Path) -> Dict[str, Any]:
        """Run verification on a project using the existing verifier infrastructure"""
        try:
            verifier_script = self.verifier_path / "pipeline_verifier" / "core" / "build_verifier.py"
            
            # Convert to absolute path to fix path resolution issue 
            absolute_project_path = project_path.resolve()
            
            cmd = [
                "python3", str(verifier_script),
                "--input", str(absolute_project_path),
                "--docker",
                "--smart-docker",
                "--verbose"
            ]
            
            print(f"      Executing: {' '.join(cmd)}")
            print(f"      Working directory: {self.verifier_path}")
            print(f"      Target path: {absolute_project_path}")
            
            start_time = datetime.datetime.now()
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(self.verifier_path)
            )
            
            end_time = datetime.datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"      Completed in {duration:.1f}s - RC: {result.returncode}")
            print(f"      STDOUT length: {len(result.stdout)} chars")
            print(f"      STDERR length: {len(result.stderr)} chars")
            
            # Print first few lines of output to verify Docker is running (testing purpose)
            if result.stdout:
                stdout_lines = result.stdout.split('\n')[:5]
                print(f"      First stdout lines: {stdout_lines}")
            
            if result.stderr and result.returncode != 0:
                stderr_lines = result.stderr.split('\n')[:3]
                print(f"      First stderr lines: {stderr_lines}")
            
            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "duration": duration
            }
            
        except subprocess.TimeoutExpired:
            print(f"      TIMEOUT after 10 minutes")
            return {
                "return_code": 124,
                "stdout": "",
                "stderr": "Verification timed out after 10 minutes",
                "success": False,
                "error": "Verification timed out"
            }
        except Exception as e:
            print(f"      EXCEPTION: {e}")
            return {
                "return_code": 125,
                "stdout": "",
                "stderr": str(e),
                "success": False,
                "error": str(e)
            }


class ResultComparator:
    """Compares verification results to determine patch effectiveness"""
    
    def compare_results(
        self,
        patch_info: PatchInfo,
        original_result: Dict[str, Any],
        patched_result: Dict[str, Any],
        start_time: datetime.datetime
    ) -> VerificationResult:
        """Compare original and patched verification results"""
        
        original_success = original_result.get("success", False)
        patched_success = patched_result.get("success", False)
        original_rc = original_result.get("return_code", 1)
        patched_rc = patched_result.get("return_code", 1)
        
        print(f"      Original result: RC={original_rc}, Success={original_success}")
        print(f"      Patched result: RC={patched_rc}, Success={patched_success}")
        
        # Determine verification status
        status, reasoning, build_success, test_success = self._analyze_results(
            original_success, patched_success, original_rc, patched_rc
        )
        
        # Generate patcher feedback for next patch refinement loop
        patcher_feedback = self._generate_patcher_feedback(
            status, patch_info, original_result, patched_result
        )
        
        verification_time = (datetime.datetime.now() - start_time).total_seconds()
        
        return VerificationResult(
            patch_id=patch_info.patch_id,
            status=status,
            reasoning=reasoning,
            confidence_score=float(patch_info.verifier_confidence) / 100.0,
            build_success=build_success,
            test_success=test_success,
            patcher_feedback=patcher_feedback,
            verification_time=verification_time
        )
    
    def _analyze_results(
        self,
        original_success: bool,
        patched_success: bool,
        original_rc: int,
        patched_rc: int
    ) -> tuple[VerificationStatus, str, bool, bool]:
        """Analyze verification results to determine status"""
        
        if not patched_success:
            if patched_rc == 1:
                return (
                    VerificationStatus.PATCH_BREAKS_BUILD,
                    "Patch introduces compilation/build errors",
                    False,
                    False
                )
            elif patched_rc == 2:
                return (
                    VerificationStatus.VERIFICATION_ERROR,
                    f"Patch verification failed with code {patched_rc}",
                    False,
                    False
                )
            else:
                return (
                    VerificationStatus.VERIFICATION_ERROR,
                    f"Patch verification failed with code {patched_rc}",
                    False,
                    False
                )
        else:
            reasoning = "Patch maintains build/test success"
            
            if original_success and patched_success:
                reasoning += " - No regressions detected"
            elif not original_success and patched_success:
                reasoning += " - Patch fixed build/test issues"
            
            return (
                VerificationStatus.PATCH_VALID,
                reasoning,
                True,
                True
            )
    
    def _generate_patcher_feedback(
        self,
        status: VerificationStatus,
        patch_info: PatchInfo,
        original_result: Dict[str, Any],
        patched_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate feedback for patch refinement (Verifier → Patcher)"""
        # TODO: handle SAFE patches for Finder loop
        
        feedback = {
            "status": status.value,
            "requires_revision": status != VerificationStatus.PATCH_VALID,
            "patch_quality_assessment": {
                "plan_clarity": len(patch_info.plan),
                "risk_assessment": "low" if "low" in patch_info.risk_notes.lower() else "medium",
                "touched_files_count": len(patch_info.touched_files)
            },
            "verification_comparison": {
                "original_success": original_result.get("success", False),
                "patched_success": patched_result.get("success", False),
                "regression_introduced": (
                    original_result.get("success", False) and
                    not patched_result.get("success", False)
                )
            },
            "recommendations": []
        }
        
        # Add specific recommendations based on status
        if status == VerificationStatus.PATCH_BREAKS_BUILD:
            feedback["recommendations"].append("Fix compilation errors introduced by patch")
            feedback["build_regression"] = True
            
        elif status == VerificationStatus.PATCH_BREAKS_TESTS:
            feedback["recommendations"].append("Fix test failures introduced by patch")
            feedback["test_regression"] = True
            
        elif status == VerificationStatus.PATCH_VALID:
            original_success = original_result.get("success", False)
            patched_success = patched_result.get("success", False)
            
            if not original_success and patched_success:
                feedback["recommendations"].append("Patch successfully fixed build/test issues")
                feedback["improvement_detected"] = True
            else:
                feedback["recommendations"].append("Patch appears valid but needs POV testing")
                
        else:  # VERIFICATION_ERROR
            feedback["recommendations"].append("Manual review required due to verification issues")
        
        # Include original patch metadata
        feedback["original_patch_confidence"] = patch_info.confidence
        feedback["cwe_matches"] = patch_info.cwe_matches
        
        return feedback


class POVTester:
    """Handles POV tests"""
    
    def run_pov_tests(self, project_path: pathlib.Path, patch_info: PatchInfo) -> Dict[str, Any]:
        """Run POV tests on patched code (placeholder for future implementation)"""
        # TODO: Implement when POV tests ready
        return {
            "pov_success": True,  # temp
            "vulnerability_eliminated": True,  # temp
            "pov_details": "POV testing not yet implemented"
        }