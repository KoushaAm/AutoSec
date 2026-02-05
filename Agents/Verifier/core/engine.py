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
        """
        Orchestrates single patch verification through all stages.
        Delegates to specialized methods for each verification step.
        """
        start_time = datetime.datetime.now()
        patch_dir = self.artifact_manager.create_patch_directory(session_dir, patch_info.patch_id)
        
        try:
            # Initialize verification context
            context = self._initialize_verification_context(patch_info, patch_dir, start_time)
            if isinstance(context, VerificationResult):  # Error during initialization
                return context
            
            # Step 1 & 2: Locate project and apply patch
            patch_result = self._apply_patch_to_project(context)
            if isinstance(patch_result, VerificationResult):  # Error during patching
                return patch_result
            
            # Step 3: Build and run existing tests
            build_result = self._run_build_and_existing_tests(context)
            if isinstance(build_result, VerificationResult):  # Build failed critically
                return build_result
            
            # Step 4: Run POV tests (if available)
            pov_result = self._run_pov_tests(context)
            
            # Step 5: Generate and run LLM tests
            llm_result = self._run_llm_tests(context)
            
            # Evaluate all results and generate final decision
            verification_result = self._evaluate_results(
                context, build_result, pov_result, llm_result
            )
            
            # Save all artifacts
            self._save_all_artifacts(
                context, build_result, pov_result, llm_result, verification_result
            )
            
            return verification_result
            
        except Exception as e:
            return ErrorHandler.create_error_result(patch_info.patch_id, str(e), start_time)
    
    def _initialize_verification_context(
        self, 
        patch_info: PatchInfo, 
        patch_dir: pathlib.Path,
        start_time: datetime.datetime
    ) -> Dict[str, Any]:
        if not patch_info.touched_files:
            return ErrorHandler.create_error_result(
                patch_info.patch_id, "No touched files specified", start_time
            )
        
        patcher_file_path = patch_info.touched_files[0]
        
        # Extract project root
        print(f"   [1/5] Locating project root...", end=" ", flush=True)
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
        
        # Convert to absolute path
        actual_file_path = pathlib.Path(patcher_file_path)
        if not actual_file_path.is_absolute():
            autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
            actual_file_path = autosec_root / actual_file_path
        
        if not actual_file_path.exists():
            print("✗")
            return ErrorHandler.create_error_result(
                patch_info.patch_id, f"File not found: {actual_file_path}", start_time
            )
        
        return {
            "patch_info": patch_info,
            "patch_dir": patch_dir,
            "project_root": project_root,
            "actual_file_path": actual_file_path,
            "start_time": start_time
        }
    
    def _apply_patch_to_project(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch to the source file in Projects/Sources/"""
        patch_info = context["patch_info"]
        patch_dir = context["patch_dir"]
        actual_file_path = context["actual_file_path"]
        start_time = context["start_time"]
        
        print(f"   [2/5] Applying patch to file...", end=" ", flush=True)
        
        # Build patch info dict
        patch_info_dict = {
            "file_path": str(actual_file_path),
            "unified_diff": patch_info.unified_diff,
            "plan": patch_info.plan,
            "safety_verification": patch_info.safety_verification
        }
        
        # Apply patch - creates {original_name}_patched.java and deletes original
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
        
        # Store results in context
        context["patch_result"] = patch_result
        context["patched_file_path"] = patched_file_path
        
        return context
    
    def _run_build_and_existing_tests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        patch_info = context["patch_info"]
        project_root = context["project_root"]
        patch_dir = context["patch_dir"]
        
        print(f"   [3/5] Building & testing project with patched file...")
        
        patched_result = self.build_runner.run_verification(
            project_root, patch_info, output_dir=patch_dir
        )
        
        print(f"      {'✓' if patched_result.get('success') else '✗'}")
        
        # Store Docker image and stack for consistency in later steps
        context["docker_image"] = patched_result.get("docker_image")
        context["stack"] = patched_result.get("stack")
        context["build_result"] = patched_result
        
        return patched_result
    
    def _run_pov_tests(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        patch_info = context["patch_info"]
        project_root = context["project_root"]
        patch_dir = context["patch_dir"]
        docker_image = context.get("docker_image")
        stack = context.get("stack")
        
        if not patch_info.pov_tests:
            print(f"   [4/5] No POV tests provided, skipping...")
            return None
        
        print(f"   [4/5] Running POV tests from Exploiter...")
        
        pov_result = self.pov_tester.run_pov_tests(
            project_root,
            docker_image,
            stack,
            patch_info.pov_tests,
            patch_dir / "pov_tests"
        )
        
        if pov_result.get("status") == "PASS":
            print(f"      ✓ POV tests passed ({pov_result['passed_pov_tests']}/{pov_result['total_pov_tests']})")
        elif pov_result.get("status") == "FAIL":
            print(f"      ✗ POV tests failed ({pov_result['failed_pov_tests']}/{pov_result['total_pov_tests']})")
        else:
            print(f"      ⊘ POV tests skipped")
        
        return pov_result
    
    def _run_llm_tests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        patch_info = context["patch_info"]
        project_root = context["project_root"]
        patch_dir = context["patch_dir"]
        docker_image = context.get("docker_image")
        stack = context.get("stack")
        
        print(f"   [5/5] Generating and running LLM security tests...")
        
        llm_result = self.llm_test_handler.generate_and_run_tests(
            project_root,
            docker_image,
            stack,
            patch_info,
            patch_dir / "llm_tests"
        )
        
        if llm_result.get("status") == "PASS":
            test_results = llm_result.get("test_execution", {}).get("test_results", {})
            print(f"      ✓ LLM tests passed ({test_results.get('passed_tests', 0)}/{test_results.get('total_tests', 0)})")
        elif llm_result.get("status") == "FAIL":
            print(f"      ✗ LLM tests failed")
        else:
            print(f"      ⊘ LLM test generation/execution skipped")
        
        return llm_result
    
    def _evaluate_results(
        self,
        context: Dict[str, Any],
        build_result: Dict[str, Any],
        pov_result: Optional[Dict[str, Any]],
        llm_result: Dict[str, Any]
    ) -> VerificationResult:
        """Evaluate all test results and generate final verification decision"""
        patch_info = context["patch_info"]
        start_time = context["start_time"]
        
        return self.result_evaluator.compare_results(
            patch_info, build_result, start_time, 
            pov_result=pov_result, 
            llm_test_result=llm_result
        )
    
    def _save_all_artifacts(
        self,
        context: Dict[str, Any],
        build_result: Dict[str, Any],
        pov_result: Optional[Dict[str, Any]],
        llm_result: Dict[str, Any],
        verification_result: VerificationResult
    ):
        patch_info = context["patch_info"]
        patch_dir = context["patch_dir"]
        patched_file_path = context["patched_file_path"]
        patch_result = context["patch_result"]
        project_root = context["project_root"]
        
        self._save_verification_artifacts(
            patch_info, patch_dir, 
            patched_file_path,
            patch_result, build_result, verification_result,
            project_root, pov_result, llm_result
        )

    def _save_verification_artifacts(self, patch_info: PatchInfo, patch_dir: pathlib.Path, 
                                   patched_file_path: pathlib.Path, patch_result: dict,
                                   patched_result: dict, 
                                   verification_result: VerificationResult,
                                   project_root: pathlib.Path, pov_result=None, llm_test_result=None):
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
                "pov_tests": pov_result or {},
                "llm_tests": llm_test_result or {},
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