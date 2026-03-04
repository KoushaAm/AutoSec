import json
import pathlib
import datetime
from typing import Dict, Any, List
from ..models.verification import VerificationResult, PatchInfo


class ArtifactManager:
    """Manages saving and organizing verification artifacts"""
    # TODO: db integration may require change for final output?
    
    def __init__(self, output_dir: pathlib.Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        self.base_output_dir = output_dir 
    
    def create_session_directory(self, fixer_input_path: str) -> pathlib.Path:
        """Create a timestamped session directory (temp)"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = self.output_dir / f"session_{timestamp}"
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
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
                        "status": r.status if isinstance(r.status, str) else r.status.value,
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
    
    def _generate_results_summary(self, results: List[VerificationResult]) -> Dict[str, int]:
        """Summary by status"""
        from ..models.verification import VerificationStatus
        
        return {
            "patch_valid": len([r for r in results if r.status == VerificationStatus.PATCH_VALID]),
            "patch_breaks_build": len([r for r in results if r.status == VerificationStatus.PATCH_BREAKS_BUILD]),
            "patch_breaks_tests": len([r for r in results if r.status == VerificationStatus.PATCH_BREAKS_TESTS]),
            "verification_error": len([r for r in results if r.status == VerificationStatus.VERIFICATION_ERROR])
        }


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
    


class ConfigManager:
    """Manages configuration and settings"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._set_defaults()
    
    def _set_defaults(self):
        # Get absolute path to Verifier/output directory
        verifier_root = pathlib.Path(__file__).parent.parent
        output_dir = verifier_root / "output"
        
        defaults = {
            "verification_timeout": 600,  # 10 minutes
            "output_directory": str(output_dir),  # Use absolute path
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