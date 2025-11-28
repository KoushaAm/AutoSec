import json
import pathlib
import shutil
import datetime
from typing import Dict, Any, List
from ..models.verification import VerificationResult, VerificationSession, PatchInfo


class ArtifactManager:
    """Manages saving and organizing verification artifacts"""
    # TODO: db integration may require change
    
    def __init__(self, output_dir: pathlib.Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
    
    def create_session_directory(self, fixer_input_path: str) -> pathlib.Path:
        """Create a timestamped session directory (temp)"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.output_dir / f"session_{timestamp}"
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def create_patch_directory(self, session_dir: pathlib.Path, patch_id: int) -> pathlib.Path:
        """Create a directory for a specific patch"""
        patch_dir = session_dir / f"patch_{patch_id}"
        patch_dir.mkdir(exist_ok=True)
        return patch_dir
    
    def save_patch_artifacts(
        self,
        patch_info: PatchInfo,
        patch_dir: pathlib.Path,
        patched_project_path: pathlib.Path,
        patch_success: bool
    ):
        """Save patch artifacts for inspection"""
        try:
            # Save original patch data
            patch_info_file = patch_dir / "patch_info.json"
            with open(patch_info_file, 'w') as f:
                json.dump(self._patch_info_to_dict(patch_info), f, indent=2)
            
            # Save unified diff
            if patch_info.unified_diff:
                diff_file = patch_dir / "patch.diff"
                diff_file.write_text(patch_info.unified_diff)
            
            # Copy files to artifacts directory for comparison
            self._save_file_comparisons(patch_info, patch_dir, patched_project_path)
            
            print(f"   Artifacts saved to: {patch_dir}")
            
        except Exception as e:
            print(f"   Warning: Could not save patch artifacts: {e}")
    
    def save_verification_logs(
        self,
        patch_dir: pathlib.Path,
        original_result: Dict[str, Any],
        patched_result: Dict[str, Any],
        verification_result: VerificationResult
    ):
        """Save only essential verification results"""
        try:
            logs_dir = patch_dir / "logs"
            logs_dir.mkdir(exist_ok=True)
            
            # Save only the verification decision (not full stdout/stderr)
            result_data = {
                "patch_id": verification_result.patch_id,
                "decision": "SAFE" if verification_result.status.value == "patch_valid" else "VULNERABLE",
                "reasoning": verification_result.reasoning,
                "build_success": verification_result.build_success,
                "requires_revision": verification_result.patcher_feedback.get('requires_revision', False)
            }
            
            (logs_dir / "verification_decision.json").write_text(json.dumps(result_data, indent=2))
            
            # Only save error logs if there were actual failures
            if not patched_result.get("success", False):
                (logs_dir / "build_errors.log").write_text(patched_result.get('stderr', ''))
            
        except Exception as e:
            print(f"   Warning: Could not save verification logs: {e}")
    
    def save_session_summary(
        self,
        results: List[VerificationResult],
        session_dir: pathlib.Path,
        fixer_input_path: str
    ):
        """Save consolidated verification results"""
        try:
            summary = {
                "session_timestamp": datetime.datetime.now().isoformat(),
                "total_patches": len(results),
                "results_summary": self._generate_results_summary(results),
                "patches": [
                    {
                        "patch_id": r.patch_id,
                        "status": r.status.value,
                        "build_success": r.build_success,
                        "requires_revision": r.patcher_feedback.get('requires_revision', False),
                        "cwe_id": r.patcher_feedback.get('cwe_matches', [{}])[0].get('cwe_id', 'Unknown')
                    }
                    for r in results
                ]
            }
            
            summary_file = session_dir / "verification_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Could not save verification summary: {e}")
    
    def _save_file_comparisons(
        self,
        patch_info: PatchInfo,
        patch_dir: pathlib.Path,
        patched_project_path: pathlib.Path
    ):
        """Before/after file comparisons"""
        artifacts_dir = patch_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        
        # Find project root for original files
        original_project_path = self._find_original_project_path()
        
        for file_path in patch_info.touched_files:
            filename = pathlib.Path(file_path).name
            
            # Copy original file
            original_file = original_project_path / filename
            if original_file.exists():
                shutil.copy2(original_file, artifacts_dir / f"{filename}.original")
            
            # Copy patched file
            patched_file = patched_project_path / filename
            if patched_file.exists():
                shutil.copy2(patched_file, artifacts_dir / f"{filename}.patched")
    
    def _find_original_project_path(self) -> pathlib.Path:
        """Find the original project path"""
        # Navigate up from current file to find AutoSec root, then to vulnerable directory
        current_file = pathlib.Path(__file__)
        # Go up to AutoSec root
        autosec_root = current_file.parent.parent.parent.parent
        vulnerable_dir = autosec_root / "Experiments" / "vulnerable"
        return vulnerable_dir
    
    def _patch_info_to_dict(self, patch_info: PatchInfo) -> Dict[str, Any]:
        """PatchInfo to dictionary for JSON serialization"""
        return {
            "patch_id": patch_info.patch_id,
            "touched_files": patch_info.touched_files,
            "cwe_matches": patch_info.cwe_matches,
            "plan": patch_info.plan,
            "confidence": patch_info.confidence,
            "verifier_confidence": patch_info.verifier_confidence,
            "risk_notes": patch_info.risk_notes,
            "assumptions": patch_info.assumptions,
            "behavior_change": patch_info.behavior_change,
            "safety_verification": patch_info.safety_verification
        }
    
    def _verification_result_to_dict(self, result: VerificationResult) -> Dict[str, Any]:
        """VerificationResult to dictionary for JSON serialization"""
        return {
            "patch_id": result.patch_id,
            "status": result.status.value,
            "reasoning": result.reasoning,
            "confidence_score": result.confidence_score,
            "build_success": result.build_success,
            "test_success": result.test_success,
            "verification_time": result.verification_time,
            "patcher_feedback": result.patcher_feedback
        }
    
    def _generate_results_summary(self, results: List[VerificationResult]) -> Dict[str, int]:
        """Summary by status"""
        from ..models.verification import VerificationStatus
        
        return {
            "patch_valid": len([r for r in results if r.status == VerificationStatus.PATCH_VALID]),
            "patch_breaks_build": len([r for r in results if r.status == VerificationStatus.PATCH_BREAKS_BUILD]),
            "patch_breaks_tests": len([r for r in results if r.status == VerificationStatus.PATCH_BREAKS_TESTS]),
            "verification_error": len([r for r in results if r.status == VerificationStatus.VERIFICATION_ERROR])
        }


class FileOperations:
    """Common file operations and path utilities"""
    
    @staticmethod
    def ensure_directory(path: pathlib.Path) -> pathlib.Path:
        """Ensure a directory exists, and create it if necessary"""
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @staticmethod
    def safe_copy_tree(source: pathlib.Path, destination: pathlib.Path) -> bool:
        """Safely copy a directory tree, handling existing destinations"""
        try:
            if destination.exists():
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            return True
        except Exception as e:
            print(f"Error copying directory tree: {e}")
            return False
    
    @staticmethod
    def clean_temp_directories(base_path: pathlib.Path, pattern: str = "patch_*"):
        """Clean up temp directories based on pattern"""
        try:
            for item in base_path.glob(pattern):
                if item.is_dir():
                    shutil.rmtree(item)
        except Exception as e:
            print(f"Warning: Could not clean temp directories: {e}")


class ErrorHandler:
    """Main error handling and reporting"""
    
    @staticmethod
    def create_error_result(
        patch_id: int,
        error_msg: str,
        start_time: datetime.datetime
    ) -> VerificationResult:
        from ..models.verification import VerificationResult, VerificationStatus
        
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
    
    @staticmethod
    def log_error(context: str, error: Exception):
        print(f"ERROR in {context}: {type(error).__name__}: {str(error)}")
    
    @staticmethod
    def log_warning(context: str, message: str):
        print(f"WARNING in {context}: {message}")


class ConfigManager:
    """Manages configuration and settings"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._set_defaults()
    
    def _set_defaults(self):
        defaults = {
            "verification_timeout": 600,  # 10 minutes
            "output_directory": "verifier/verifier_output",
            "preserve_artifacts": True,
            "verbose_logging": True
        }
        
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        self.config[key] = value