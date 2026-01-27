import json
import pathlib
import datetime
import sys
from typing import Dict, Any, List, Optional

from ..models.verification import VerificationResult, PatchInfo
from ..handlers.patch_handler import PatchParser, ProjectManager
from ..handlers.verification_handler import BuildVerifier, ResultComparator, POVTester
from ..utils.file_operations import ArtifactManager, ErrorHandler, ConfigManager

# Import LLM patch applicator from within the module
from .patch_applicator import LLMPatchApplicator
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from constants import Model


class VerifierCore:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config_manager = ConfigManager(config)
        self.artifact_manager = ArtifactManager(
            pathlib.Path(self.config_manager.get("output_directory"))
        )
        
        # Initialize handlers
        self.patch_parser = PatchParser()
        self.patch_applicator = LLMPatchApplicator(model=Model.LLAMA3)  # No dry_run flag needed
        self.project_manager = ProjectManager()
        self.build_verifier = BuildVerifier()
        self.result_comparator = ResultComparator()
        self.pov_tester = POVTester()  # TODO: not yet implemented
    
    def verify_fixer_output(self, fixer_json_path: str) -> List[VerificationResult]:
        """Patch validation entry point"""
        with open(fixer_json_path, 'r') as f:
            fixer_data = json.load(f)
        
        results = []
        session_dir = self.artifact_manager.create_session_directory(fixer_json_path)
        
        for patch_data in fixer_data.get('patches', []):
            patch_info = self.patch_parser.parse_fixer_patch(patch_data)
            cwe_id = patch_info.cwe_matches[0]['cwe_id'] if patch_info.cwe_matches else 'Unknown'
            
            print(f"Verifying patch {patch_info.patch_id} for {cwe_id}")
            
            result = self._verify_single_patch(patch_info, session_dir)
            results.append(result)
        
        # Save session results
        self.artifact_manager.save_session_summary(results, session_dir, fixer_json_path)
        
        return results
    
    def _verify_single_patch(self, patch_info: PatchInfo, session_dir: pathlib.Path) -> VerificationResult:
        """Single patch verification - full project builds with proper file substitution"""
        start_time = datetime.datetime.now()
        patch_dir = self.artifact_manager.create_patch_directory(session_dir, patch_info.patch_id)
        
        try:
            if not patch_info.touched_files:
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "No touched files specified", start_time
                )
            
            # Get the vulnerable project directory (contains all vulnerable files)
            vulnerable_project_path = self.project_manager.find_project_root(patch_info.touched_files[0])
            
            # Extract the specific file that will be patched
            target_file_path = patch_info.touched_files[0]
            target_filename = pathlib.Path(target_file_path).name
            
            # Step 1: Build original vulnerable project
            print(f"   [1/4] Building original project ({target_filename})...", end=" ", flush=True)
            original_result = self.build_verifier.run_verification(vulnerable_project_path)
            print(f"{'✓' if original_result.get('success') else '✗'}")
            
            # Step 2: Apply patch
            print(f"   [2/4] Applying patch...", end=" ", flush=True)
            
            patch_info_dict = {
                "unified_diff": patch_info.unified_diff,
                "plan": patch_info.plan,
                "safety_verification": patch_info.safety_verification,
                "touched_files": patch_info.touched_files
            }
            
            patch_result = self.patch_applicator.apply_patch_to_directory(
                source_dir=vulnerable_project_path,
                patch_info=patch_info_dict,
                output_dir=patch_dir
            )
            
            if patch_result["status"] not in ["success", "partial"]:
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, f"Patch application failed: {patch_result.get('error', 'Unknown error')}", start_time
                )
            
            patched_file_info = patch_result["file_results"][0] if patch_result["file_results"] else None
            if not patched_file_info or patched_file_info["status"] != "success":
                print("✗")
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "No successful patch application results", start_time
                )
            
            patched_file_path = pathlib.Path(patched_file_info["output_path"])
            print("✓")
            
            # Step 3: Create verification project
            print(f"   [3/4] Creating patched project...", end=" ", flush=True)
            verification_project_dir = patch_dir / "verification_project"
            verification_project_dir.mkdir(exist_ok=True)
            
            import shutil
            for item in vulnerable_project_path.iterdir():
                if item.is_file():
                    dest_file = verification_project_dir / item.name
                    shutil.copy2(item, dest_file)
                elif item.is_dir():
                    dest_dir = verification_project_dir / item.name
                    shutil.copytree(item, dest_dir, dirs_exist_ok=True)
            
            target_file_in_verification = verification_project_dir / target_filename
            shutil.copy2(patched_file_path, target_file_in_verification)
            print("✓")
            
            # Step 4: Build patched project
            print(f"   [4/4] Building patched project...", end=" ", flush=True)
            patched_result = self.build_verifier.run_verification(verification_project_dir)
            print(f"{'✓' if patched_result.get('success') else '✗'}")
            
            # Compare and generate decision
            verification_result = self.result_comparator.compare_results(
                patch_info, original_result, patched_result, start_time
            )
            
            # Save artifacts
            self._save_verification_artifacts(
                patch_info, patch_dir, patched_file_path, patch_result, 
                original_result, patched_result, verification_result,
                target_filename, vulnerable_project_path, verification_project_dir
            )
            
            return verification_result
            
        except Exception as e:
            return ErrorHandler.create_error_result(patch_info.patch_id, str(e), start_time)

    def _save_verification_artifacts(self, patch_info: PatchInfo, patch_dir: pathlib.Path, 
                                   patched_file_path: pathlib.Path, patch_result: dict,
                                   original_result: dict, patched_result: dict, 
                                   verification_result: VerificationResult,
                                   target_filename: str, vulnerable_project_path: pathlib.Path,
                                   verification_project_dir: pathlib.Path):
        """Save verification artifacts"""
        try:
            # Save detailed verification results
            results_file = patch_dir / "verification_results.json"
            results_data = {
                "patch_application": {
                    "status": patch_result["status"],
                    "patched_file": patched_file_path.name,
                    "model_used": patch_result.get("model_used", "unknown")
                },
                "build_verification": {
                    "original": {
                        "success": original_result.get("success", False),
                        "return_code": original_result.get("return_code", -1),
                        "duration": original_result.get("duration", 0),
                        "tested_project": str(vulnerable_project_path)
                    },
                    "patched": {
                        "success": patched_result.get("success", False),
                        "return_code": patched_result.get("return_code", -1),
                        "duration": patched_result.get("duration", 0),
                        "tested_project": str(verification_project_dir)
                    }
                },
                "final_decision": {
                    "status": verification_result.status.value,
                    "reasoning": verification_result.reasoning,
                    "confidence": verification_result.confidence_score,
                    "verification_time": verification_result.verification_time
                }
            }
            
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            
            # Create unified diff file
            diff_file = patch_dir / "patch.diff"
            diff_file.write_text(patch_info.unified_diff, encoding='utf-8')
            
        except Exception as e:
            print(f"   ⚠️  Failed to save artifacts: {e}")

def create_verifier(config: Optional[Dict[str, Any]] = None) -> VerifierCore:
    """Factory function to create a configured verifier instance"""
    return VerifierCore(config)