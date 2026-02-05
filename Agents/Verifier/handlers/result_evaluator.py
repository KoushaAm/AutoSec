"""
Result Evaluator

Evaluating results and preparing for patch refinement
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
        start_time: datetime.datetime,
        pov_result: Dict[str, Any] = None,
        llm_test_result: Dict[str, Any] = None
    ) -> VerificationResult:
        """Evaluate patched code verification results including POV and LLM tests"""
        
        patched_success = patched_result.get("success", False)
        patched_rc = patched_result.get("return_code", 1)
        
        # POV test results
        pov_passed = True
        if pov_result:
            pov_status = pov_result.get("status")
            pov_passed = pov_status == "PASS" or pov_status == "SKIP"
            if pov_status == "FAIL":
                print(f"      ⚠️  POV tests FAILED - vulnerability still exploitable!")
        
        # LLM test results
        llm_passed = True
        if llm_test_result:
            llm_status = llm_test_result.get("status")
            llm_passed = llm_status == "PASS" or llm_status == "SKIP"
            if llm_status == "FAIL":
                print(f"      ⚠️  LLM security tests FAILED!")
        
        print(f"      Patched result: RC={patched_rc}, Build={patched_success}, POV={pov_passed}, LLM={llm_passed}")
        
        # Determine verification status considering all test results
        status, reasoning, build_success, test_success = self._analyze_results(
            patched_success, patched_rc, pov_passed, llm_passed
        )
        
        # Generate patcher feedback for potential refinement
        patcher_feedback = self._generate_patcher_feedback(
            status, patch_info, patched_result, pov_result, llm_test_result
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
        patched_rc: int,
        pov_passed: bool = True,
        llm_passed: bool = True
    ) -> Tuple[VerificationStatus, str, bool, bool]:
        
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
        
        # Build succeeded, now check POV and LLM tests
        if not pov_passed:
            return (
                VerificationStatus.PATCH_BREAKS_TESTS,
                "Patch passes build but POV tests FAILED - vulnerability still exploitable",
                True,
                False
            )
        
        if not llm_passed:
            return (
                VerificationStatus.PATCH_BREAKS_TESTS,
                "Patch passes build but LLM security tests FAILED",
                True,
                False
            )
        
        # All tests passed
        return (
            VerificationStatus.PATCH_VALID,
            "Patch builds successfully and passes all tests (existing + POV + LLM)",
            True,
            True
        )
    
    def _generate_patcher_feedback(
        self,
        status: VerificationStatus,
        patch_info: PatchInfo,
        patched_result: Dict[str, Any],
        pov_result: Dict[str, Any] = None,
        llm_test_result: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate feedback for patch refinement including POV and LLM test results"""
        
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
            "pov_tests": pov_result or {},
            "llm_tests": llm_test_result or {},
            "recommendations": []
        }
        
        # Add specific recommendations based on status
        if status == VerificationStatus.PATCH_BREAKS_BUILD:
            feedback["recommendations"].append("Fix compilation errors introduced by patch")
            feedback["build_regression"] = True
            
        elif status == VerificationStatus.PATCH_BREAKS_TESTS:
            # Check which tests failed
            if pov_result and pov_result.get("status") == "FAIL":
                feedback["recommendations"].append("POV tests FAILED - vulnerability is still exploitable after patching")
                feedback["pov_regression"] = True
            
            if llm_test_result and llm_test_result.get("status") == "FAIL":
                feedback["recommendations"].append("LLM security tests FAILED - patch may not fully address security issues")
                feedback["llm_test_regression"] = True
            
            if not (pov_result and pov_result.get("status") == "FAIL") and not (llm_test_result and llm_test_result.get("status") == "FAIL"):
                feedback["recommendations"].append("Fix test failures introduced by patch")
            
            feedback["test_regression"] = True
            
        elif status == VerificationStatus.PATCH_VALID:
            feedback["recommendations"].append("Patch validated - builds and passes all tests (existing + POV + LLM)")
            feedback["patch_accepted"] = True
                
        else:  # VERIFICATION_ERROR
            feedback["recommendations"].append("Manual review required due to verification issues")
        
        # Include original patch metadata
        feedback["original_patch_confidence"] = patch_info.confidence
        feedback["cwe_matches"] = patch_info.cwe_matches
        
        return feedback
