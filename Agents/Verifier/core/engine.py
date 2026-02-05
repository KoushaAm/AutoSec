import json
import pathlib
import datetime
import sys
from typing import Dict, Any, List, Optional

from ..models.verification import VerificationResult, PatchInfo
from ..handlers.patch_parser import PatchParser, ProjectManager
from ..handlers.build_handler import DockerBuildRunner
from ..handlers.pov_handler import POVTestRunner
from ..handlers.llm_test_handler import LLMTestHandler
from ..handlers.result_evaluator import ResultEvaluator
from ..utils.file_ops import ArtifactManager, ErrorHandler, ConfigManager

# Import LLM patch applicator from within the module
from .patch_applicator import LLMPatchApplicator
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from constants.models import Model


class VerifierCore:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config_manager = ConfigManager(config)
        self.artifact_manager = ArtifactManager(
            pathlib.Path(self.config_manager.get("output_directory"))
        )
        
        self.patch_parser = PatchParser()
        self.patch_applicator = LLMPatchApplicator(model=Model.LLAMA3)
        self.project_manager = ProjectManager()
        self.build_runner = DockerBuildRunner()
        self.pov_tester = POVTestRunner()
        self.llm_test_handler = LLMTestHandler(verbose=True)
        self.result_evaluator = ResultEvaluator()
    
    def verify_fixer_output(self, fixer_json_path: str) -> List[VerificationResult]:
        """Patch validation entry point"""
        with open(fixer_json_path, 'r') as f:
            fixer_data = json.load(f)
        
        results = []
        session_dir = self.artifact_manager.create_session_directory(fixer_json_path)
        
        # Check if Patcher output is empty
        patches = fixer_data.get('patches', [])
        if not patches:
            print("\n⚠️  WARNING: No patches found in Patcher output")
            print("   The Patcher may have failed to generate patches, or the input file is empty.")
            print(f"   Input file: {fixer_json_path}")
            
            # Save empty session summary with warning
            self.artifact_manager.save_session_summary(results, session_dir, fixer_json_path)
            return results
        
        print(f"\nFound {len(patches)} patch(es) to verify\n")
        
        for patch_data in patches:
            patch_info = self.patch_parser.parse_fixer_patch(patch_data)
            cwe_id = patch_info.cwe_matches[0]['cwe_id'] if patch_info.cwe_matches else 'Unknown'
            
            print(f"Verifying patch {patch_info.patch_id} for {cwe_id}")
            
            result = self._verify_single_patch(patch_info, session_dir)
            results.append(result)
        
        # Save session results
        self.artifact_manager.save_session_summary(results, session_dir, fixer_json_path)
        
        return results
    
    def _verify_single_patch(self, patch_info: PatchInfo, session_dir: pathlib.Path) -> VerificationResult:
        """Single patch verification. Only verify patched code builds and passes tests"""
        start_time = datetime.datetime.now()
        patch_dir = self.artifact_manager.create_patch_directory(session_dir, patch_info.patch_id)
        
        try:
            if not patch_info.touched_files:
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "No touched files specified", start_time
                )
            
            # Get file path from Patcher output
            # Expected : "Projects/Sources/project_name/src/main/File.java"
            patcher_file_path = patch_info.touched_files[0]
            
            # Extract project root from the file path
            print(f"   [1/3] Locating project root...", end=" ", flush=True)
            try:
                project_root = self.project_manager.find_project_root(patcher_file_path)
            except ValueError as e:
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, str(e), start_time
                )
            
            if not project_root.exists():
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, f"Project root does not exist: {project_root}", start_time
                )
            print("✓")
            
            # Applying patch directly to file in Projects/Sources/
            print(f"   [2/3] Applying patch to file...", end=" ", flush=True)
            
            # Convert to absolute path (if needed)
            actual_file_path = pathlib.Path(patcher_file_path)
            if not actual_file_path.is_absolute():
                # Make it absolute relative to AutoSec root
                autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
                actual_file_path = autosec_root / actual_file_path
            
            if not actual_file_path.exists():
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, f"File not found: {actual_file_path}", start_time
                )
            
            # Build patch info dict with actual file path
            patch_info_dict = {
                "file_path": str(actual_file_path),
                "unified_diff": patch_info.unified_diff,
                "plan": patch_info.plan,
                "safety_verification": patch_info.safety_verification
            }
            
            # Apply patch - create {original_name}_patched.java and delete original
            patch_result = self.patch_applicator.apply_patch(patch_info_dict)
            
            if patch_result["status"] != "success":
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, 
                    f"Patch application failed: {patch_result.get('error', 'Unknown error')}", 
                    start_time
                )
            
            patched_file_path = pathlib.Path(patch_result["patched_file"])
            print("✓")
            print(f"      Created: {patched_file_path.name}")
            
            # Save patch application artifacts
            patch_app_dir = patch_dir / "patch_application"
            patch_app_dir.mkdir(parents=True, exist_ok=True)
            self._save_patch_application_artifacts(patch_info, patch_result, patch_app_dir)
            
            # Build and test project with patched file
            print(f"   [3/3] Building & testing project with patched file...")
            patched_result = self.build_runner.run_verification(
                project_root, patch_info, output_dir=patch_dir
            )
            print(f"      {'✓' if patched_result.get('success') else '✗'}")
            
            # Generate decision based only on patched result
            verification_result = self.result_evaluator.compare_results(
                patch_info, patched_result, start_time
            )
            
            # Save artifacts
            self._save_verification_artifacts(
                patch_info, patch_dir, 
                patched_file_path,
                patch_result, patched_result, verification_result,
                project_root
            )
            
            return verification_result
            
        except Exception as e:
            return ErrorHandler.create_error_result(patch_info.patch_id, str(e), start_time)

    def _save_verification_artifacts(self, patch_info: PatchInfo, patch_dir: pathlib.Path, 
                                   patched_file_path: pathlib.Path, patch_result: dict,
                                   patched_result: dict, 
                                   verification_result: VerificationResult,
                                   project_root: pathlib.Path):
        """Save verification artifacts with organized test results"""
        try:
            import json
            
            # Save detailed verification results
            results_file = patch_dir / "verification_results.json"
            results_data = {
                "patch_application": {
                    "status": patch_result["status"],
                    "original_file": patch_result.get("original_file", ""),
                    "patched_file": str(patched_file_path),
                    "model_used": patch_result.get("model_used", "unknown")
                },
                "build_verification": {
                    "patched": {
                        "success": patched_result.get("success", False),
                        "return_code": patched_result.get("return_code", -1),
                        "duration": patched_result.get("duration", 0),
                        "project_root": str(project_root)
                    }
                },
                "test_discovery": patched_result.get("test_discovery", {
                    "has_tests": False,
                    "test_count": 0,
                    "message": "No test discovery performed"
                }),
                "test_execution": patched_result.get("test_execution", {
                    "status": "SKIP",
                    "message": "No tests executed"
                }),
                "final_decision": {
                    "status": verification_result.status.value,
                    "reasoning": verification_result.reasoning,
                    "confidence": verification_result.confidence_score,
                    "verification_time": verification_result.verification_time,
                    "build_success": verification_result.build_success,
                    "test_success": verification_result.test_success
                }
            }
            
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            
            # Create unified diff file
            diff_file = patch_dir / "patch.diff"
            diff_file.write_text(patch_info.unified_diff, encoding='utf-8')
            
            # Save test results summary if tests were executed
            test_execution = patched_result.get("test_execution", {})
            if test_execution.get("test_results", {}).get("total_tests", 0) > 0:
                test_summary_file = patch_dir / "test_summary.json"
                test_summary = {
                    "test_results": test_execution.get("test_results", {}),
                    "test_discovery": patched_result.get("test_discovery", {}),
                    "execution_details": {
                        "command": test_execution.get("command", ""),
                        "duration_seconds": test_execution.get("duration_seconds", 0),
                        "return_code": test_execution.get("return_code", -1)
                    }
                }
                with open(test_summary_file, 'w') as f:
                    json.dump(test_summary, f, indent=2)
                
                print(f"   📊 Test summary saved to: {test_summary_file.name}")
            
        except Exception as e:
            print(f"   ⚠️  Failed to save artifacts: {e}")

    def _save_patch_application_artifacts(self, patch_info: PatchInfo, patch_result: dict, patch_app_dir: pathlib.Path):
        """Save patch application artifacts"""
        try:
            patch_app_file = patch_app_dir / "patch_application.json"
            patch_app_data = {
                "patch_id": patch_info.patch_id,
                "status": patch_result["status"],
                "original_file": patch_result.get("original_file", ""),
                "patched_file": patch_result.get("patched_file", ""),
                "model_used": patch_result.get("model_used", "unknown"),
                "error": patch_result.get("error", "")
            }
            with open(patch_app_file, 'w') as f:
                json.dump(patch_app_data, f, indent=2)
        except Exception as e:
            print(f"   ⚠️  Failed to save patch application artifacts: {e}")

def create_verifier(config: Optional[Dict[str, Any]] = None) -> VerifierCore:
    """Factory function to create a configured verifier instance"""
    return VerifierCore(config)