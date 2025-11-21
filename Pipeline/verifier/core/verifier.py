import json
import pathlib
import datetime
from typing import Dict, Any, List, Optional

from ..models.verification import VerificationResult, PatchInfo
from ..handlers.patch_handler import PatchParser, PatchApplicator, ProjectManager
from ..handlers.verification_handler import BuildVerifier, ResultComparator, POVTester
from ..utils.file_operations import ArtifactManager, ErrorHandler, ConfigManager


class VerifierCore:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config_manager = ConfigManager(config)
        self.artifact_manager = ArtifactManager(
            pathlib.Path(self.config_manager.get("output_directory"))
        )
        
        # Initialize handlers
        self.patch_parser = PatchParser()
        self.patch_applicator = PatchApplicator()
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
        """Single patch verification"""
        start_time = datetime.datetime.now()
        patch_dir = self.artifact_manager.create_patch_directory(session_dir, patch_info.patch_id)
        
        try:
            if not patch_info.touched_files:
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "No touched files specified", start_time
                )
            
            original_project_path = self.project_manager.find_project_root(patch_info.touched_files[0])
            
            # Run verification on original and patched code
            original_result = self.build_verifier.run_verification(original_project_path)
            
            # Create patched copy and apply patch
            patched_project_path = patch_dir / "patched_project"
            copy_success = self.project_manager.create_patched_copy(
                original_project_path, patched_project_path, patch_info.touched_files
            )
            
            if not copy_success:
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "Failed to create project copy", start_time
                )
            
            patch_success = self.patch_applicator.apply_patch(patch_info, patched_project_path)
            
            # Save artifacts
            self.artifact_manager.save_patch_artifacts(
                patch_info, patch_dir, patched_project_path, patch_success
            )
            
            if not patch_success:
                return ErrorHandler.create_error_result(
                    patch_info.patch_id, "Failed to apply patch", start_time
                )
            
            # Verify patched code
            patched_result = self.build_verifier.run_verification(patched_project_path)
            
            # Generate verification decision
            verification_result = self.result_comparator.compare_results(
                patch_info, original_result, patched_result, start_time
            )
            
            # Save verification decision
            self.artifact_manager.save_verification_logs(
                patch_dir, original_result, patched_result, verification_result
            )
            
            return verification_result
            
        except Exception as e:
            return ErrorHandler.create_error_result(patch_info.patch_id, str(e), start_time)


def create_verifier(config: Optional[Dict[str, Any]] = None) -> VerifierCore:
    """Factory function to create a configured verifier instance"""
    return VerifierCore(config)