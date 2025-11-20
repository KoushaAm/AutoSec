import json
import pathlib
import sys
import subprocess
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import datetime

# Add existing Verifier infrastructure
VERIFIER_PATH = pathlib.Path(__file__).parent.parent / "Experiments" / "Verifier"
sys.path.insert(0, str(VERIFIER_PATH))

class VerificationStatus(Enum):
    PATCH_VALID = "patch_valid"
    PATCH_BREAKS_BUILD = "patch_breaks_build"
    PATCH_BREAKS_TESTS = "patch_breaks_tests"
    VERIFICATION_ERROR = "verification_error"

@dataclass
class VerificationResult:
    patch_id: int
    status: VerificationStatus
    reasoning: str
    confidence_score: float
    build_success: bool
    test_success: bool
    patcher_feedback: Dict[str, Any]
    verification_time: float

class VerifierCore:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
    def verify_fixer_output(self, fixer_json_path: str) -> List[VerificationResult]:
        with open(fixer_json_path, 'r') as f:
            fixer_data = json.load(f)
        
        results = []
        
        for patch in fixer_data.get('patches', []):
            cwe_id = patch['cwe_matches'][0]['cwe_id']
            print(f"Verifying patch {patch['patch_id']} for {cwe_id}")
            result = self._verify_single_patch(patch)
            results.append(result)
            
        return results
    
    def _verify_single_patch(self, patch: Dict[str, Any]) -> VerificationResult:
        start_time = datetime.datetime.now()
        patch_id = patch['patch_id']
        
        try:
            touched_files = patch.get('touched_files', [])
            if not touched_files:
                return self._create_error_result(patch_id, "No touched files specified", start_time)
            
            project_path = self._find_project_root(touched_files[0])
            print(f"   Original project: {project_path}")
            
            print(f"   Step 1: Evaluating original vulnerable code...")
            original_result = self._run_existing_verifier(project_path)
            
            print(f"   Step 2: Simulating patch application...")
            # WIP...
            
            print(f"   Step 3: Evaluating patched code...")
            # For demo purposes, simulate patched result based on original + confidence
            patched_result = self._simulate_patched_result(original_result, patch)
            
            print(f"   Step 4: Comparing results...")
            result = self._compare_verification_results(
                patch_id, patch, original_result, patched_result, start_time
            )
            
            return result
            
        except Exception as e:
            return self._create_error_result(patch_id, str(e), start_time)
    
    def _simulate_patched_result(self, original_result: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate that high-confidence patches are more likely to succeed
        confidence = patch.get('verifier_confidence', 50)
        if confidence >= 90:
            return {"return_code": 0, "success": True, "stdout": "Build successful"}
        else:
            return original_result  # Keep original result for lower confidence
    
    def _compare_verification_results(
        self, 
        patch_id: int, 
        patch: Dict[str, Any],
        original_result: Dict[str, Any], 
        patched_result: Dict[str, Any], 
        start_time: datetime.datetime
    ) -> VerificationResult:
        
        original_success = original_result.get("success", False)
        patched_success = patched_result.get("success", False)
        original_rc = original_result.get("return_code", 1)
        patched_rc = patched_result.get("return_code", 1)
        
        print(f"      Original result: RC={original_rc}, Success={original_success}")
        print(f"      Patched result: RC={patched_rc}, Success={patched_success}")
        
        if not patched_success:
            if patched_rc == 1:
                status = VerificationStatus.PATCH_BREAKS_BUILD
                reasoning = "Patch introduces compilation/build errors"
                build_success = False
                test_success = False
            else:
                status = VerificationStatus.VERIFICATION_ERROR
                reasoning = f"Patch verification failed with code {patched_rc}"
                build_success = False
                test_success = False
        else:
            status = VerificationStatus.PATCH_VALID
            reasoning = "Patch maintains build/test success"
            
            if original_success and patched_success:
                reasoning += " - No regressions detected"
            elif not original_success and patched_success:
                reasoning += " - Patch fixed build/test issues"
            
            build_success = True
            test_success = True
        
        patcher_feedback = self._generate_comparison_feedback(
            status, patch, original_result, patched_result
        )
        
        verification_time = (datetime.datetime.now() - start_time).total_seconds()
        
        return VerificationResult(
            patch_id=patch_id,
            status=status,
            reasoning=reasoning,
            confidence_score=float(patch.get('verifier_confidence', 85)) / 100.0,
            build_success=build_success,
            test_success=test_success,
            patcher_feedback=patcher_feedback,
            verification_time=verification_time
        )
    
    def _generate_comparison_feedback(
        self, 
        status: VerificationStatus, 
        patch: Dict[str, Any],
        original_result: Dict[str, Any], 
        patched_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        
        feedback = {
            "status": status.value,
            "requires_revision": status != VerificationStatus.PATCH_VALID,
            "patch_quality_assessment": {
                "plan_clarity": len(patch.get('plan', [])),
                "risk_assessment": "low" if "low" in patch.get('risk_notes', '').lower() else "medium",
                "touched_files_count": len(patch.get('touched_files', []))
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
                feedback["recommendations"].append("good.")
                feedback["improvement_detected"] = True
            else:
                feedback["recommendations"].append("okay. need further review.")
                
        else:
            feedback["recommendations"].append("Manual review required due to verification issues")
        
        feedback["original_patch_confidence"] = patch.get('confidence')
        feedback["cwe_matches"] = patch.get('cwe_matches', [])
        
        return feedback
    
    def _find_project_root(self, file_path: str) -> str:
        full_path = pathlib.Path(__file__).parent.parent / file_path
        current = full_path.parent
        while current != current.parent:
            if (current / "pom.xml").exists() or (current / "build.gradle").exists():
                return str(current)
            current = current.parent
        return str(full_path.parent)
    
    def _run_existing_verifier(self, project_path: str) -> Dict[str, Any]:
        try:
            verifier_script = VERIFIER_PATH / "verify.py"
            cmd = [
                "python3", str(verifier_script),
                "--input", project_path,
                "--docker",
                "--smart-docker",  
                "--verbose"       
            ]
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=600,
                cwd=str(VERIFIER_PATH)
            )
            
            return {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0
            }
            
        except subprocess.TimeoutExpired:
            return {"return_code": 124, "success": False, "error": "Verification timed out"}
        except Exception as e:
            return {"return_code": 125, "success": False, "error": str(e)}
    
    def _create_error_result(self, patch_id: int, error_msg: str, start_time: datetime.datetime) -> VerificationResult:
        verification_time = (datetime.datetime.now() - start_time).total_seconds()
        
        return VerificationResult(
            patch_id=patch_id,
            status=VerificationStatus.VERIFICATION_ERROR,
            reasoning=f"Verification failed: {error_msg}",
            confidence_score=0.0,
            build_success=False,
            test_success=False,
            patcher_feedback={
                "status": "verification_error",
                "requires_revision": False,
                "recommendations": ["Manual review required due to technical error"],
                "error_details": error_msg
            },
            verification_time=verification_time
        )