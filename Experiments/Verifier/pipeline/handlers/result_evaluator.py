"""
Result Evaluator

Evaluates verification results and generates feedback for the Patcher agent.
Determines whether a patch is valid, breaks build, or breaks tests.
"""
import datetime
from typing import Dict, Any, Tuple
from ..models.verification import VerificationResult, VerificationStatus, PatchInfo


class ResultEvaluator:
    """Evaluates verification results to determine patch effectiveness"""
    
    def compare_results(
        self,
        patch_info: PatchInfo,
        patched_result: Dict[str, Any],
        start_time: datetime.datetime
    ) -> VerificationResult:
        """Evaluate patched code verification results (no pre-patch comparison needed)"""
        
        patched_success = patched_result.get("success", False)
        patched_rc = patched_result.get("return_code", 1)
        
        print(f"      Patched result: RC={patched_rc}, Success={patched_success}")
        
        # Determine verification status
        status, reasoning, build_success, test_success = self._analyze_results(
            patched_success, patched_rc
        )
        
        # Generate patcher feedback for potential refinement
        patcher_feedback = self._generate_patcher_feedback(
            status, patch_info, patched_result
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
        patched_success: bool,
        patched_rc: int
    ) -> Tuple[VerificationStatus, str, bool, bool]:
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
                    VerificationStatus.PATCH_BREAKS_TESTS,
                    "Patch causes test failures",
                    True,
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
            # Success - patch builds and tests pass
            return (
                VerificationStatus.PATCH_VALID,
                "Patch builds successfully and passes all tests",
                True,
                True
            )
    
    def _generate_patcher_feedback(
        self,
        status: VerificationStatus,
        patch_info: PatchInfo,
        patched_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate feedback for patch refinement (Verifier → Patcher)"""
        
        feedback = {
            "status": status.value,
            "requires_revision": status != VerificationStatus.PATCH_VALID,
            "patch_quality_assessment": {
                "plan_clarity": len(patch_info.plan),
                "risk_assessment": "low" if "low" in patch_info.risk_notes.lower() else "medium",
                "touched_files_count": len(patch_info.touched_files)
            },
            "verification_result": {
                "patched_success": patched_result.get("success", False),
                "return_code": patched_result.get("return_code", -1),
                "duration": patched_result.get("duration", 0)
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
            feedback["recommendations"].append("Patch validated - builds and tests pass")
            feedback["patch_accepted"] = True
                
        else:  # VERIFICATION_ERROR
            feedback["recommendations"].append("Manual review required due to verification issues")
        
        # Include original patch metadata
        feedback["original_patch_confidence"] = patch_info.confidence
        feedback["cwe_matches"] = patch_info.cwe_matches
        
        return feedback
