import json
import pathlib
import datetime
import sys
import shutil
import difflib
from typing import Dict, Any, List, Optional

from ..models.verification import VerificationResult, PatchInfo
from ..handlers.patch_parser import PatchParser, ProjectManager
from ..handlers.build_handler import DockerBuildRunner
from ..utils.file_ops import ArtifactManager, ErrorHandler, ConfigManager

# Import LLM patch applicator from within the module
from .patch_applicator import LLMPatchApplicator
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))
from constants.models import Model
import config as verifier_config


class VerifierCore:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config_manager = ConfigManager(config)
        self.artifact_manager = ArtifactManager(
            pathlib.Path(self.config_manager.get("output_directory"))
        )
        
        self.patch_parser = PatchParser()
        self.patch_applicator = LLMPatchApplicator(model=verifier_config.CURRENT_MODEL)
        self.project_manager = ProjectManager()
        self.build_runner = DockerBuildRunner()
    
    def verify_fixer_output(self, fixer_json_path: str, project_name: str = "") -> List[VerificationResult]:
        """
        Workflow:
        
        1. Apply all patches to Projects/Sources/<project>/ 
        2. Check code diff (with logging)
        3. Build the project in Docker (verify patches compile)
        4. Run all tests (project's tests + POV)
        5. Log: build/test results, Docker stdout/stderr, LLM I/O, file paths
        
        Args:
            fixer_json_path: Path to Patcher's output manifest
        """
        with open(fixer_json_path, 'r') as f:
            fixer_data = json.load(f)
        
        session_dir = self.artifact_manager.create_session_directory(fixer_json_path, project_name=project_name)
        
        # Check if Patcher output is empty
        patches = fixer_data.get('patches', [])
        if not patches:
            print("\n⚠️  WARNING: No patches found in Patcher output")
            print("   The Patcher may have failed to generate patches, or the input file is empty.")
            print(f"   Input file: {fixer_json_path}")
            
            self.artifact_manager.save_session_summary([], session_dir, fixer_json_path)
            return []
        
        print(f"\nFound {len(patches)} patch(es) to apply\n")
        
        manifest_dir = pathlib.Path(fixer_json_path).parent
        
        # Load all patch data
        patch_infos = []
        for patch_entry in patches:
            artifact_path = patch_entry.get('artifact_path', '')
            
            # Convert Docker path to local path if needed
            if artifact_path.startswith('/workspaces'):
                patch_id = patch_entry.get('patch_id', 0)
                artifact_path = str(manifest_dir / f"patch_{patch_id:03d}.json")
            
            if not pathlib.Path(artifact_path).exists():
                print(f"❌ Patch file not found: {artifact_path}")
                continue
            
            # Load the actual patch data
            with open(artifact_path, 'r') as f:
                patch_data = json.load(f)
            
            patch_info = self.patch_parser.parse_fixer_patch(patch_data)
            patch_infos.append(patch_info)
        
        if not patch_infos:
            print("❌ No valid patches found")
            self.artifact_manager.save_session_summary([], session_dir, fixer_json_path)
            return []
        
        # target file does not exist check
        autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
        valid_patches = []
        rejected_count = 0
        
        for pi in patch_infos:
            file_path = pi.touched_files[0] if pi.touched_files else ""
            abs_path = pathlib.Path(file_path) if pathlib.Path(file_path).is_absolute() else autosec_root / file_path
            
            if not abs_path.exists():
                print(f"   ✗ Rejected patch {pi.patch_id}: file not found → {file_path}")
                rejected_count += 1
            else:
                valid_patches.append(pi)
        
        if rejected_count:
            print(f"\n⚠️  Rejected {rejected_count}/{len(patch_infos)} patch(es) with invalid file paths")
        
        if not valid_patches:
            print("❌ All patches rejected — no valid file paths")
            self.artifact_manager.save_session_summary([], session_dir, fixer_json_path)
            return []
        
        print(f"✓ {len(valid_patches)} patch(es) passed file-path validation\n")
        
        # verify all valid patches together
        result = self._verify_all_patches_simple(valid_patches, session_dir)
        
        # Save session results
        self.artifact_manager.save_session_summary([result], session_dir, fixer_json_path)
        
        return [result]
    
    def _verify_all_patches_simple(
        self, 
        patch_infos: List[PatchInfo], 
        session_dir: pathlib.Path,
    ) -> VerificationResult:
        """
        Verification workflow:
        1. Apply patches 
        2. Check code diff (compare before/after)  
        3. Build in Docker
        4. Run all tests 
        
        All stages produce structured logs saved to session_dir
        """
        start_time = datetime.datetime.now()
        
        # Structured log accumulator — saved to verification_results.json at end
        verification_log = {
            "session_dir": str(session_dir),
            "start_time": start_time.isoformat(),
            "stages": {},
        }
        
        print("="*80)
        print("VERIFICATION WORKFLOW")
        print("="*80)
        
        # Determine project root
        first_patch_file = patch_infos[0].touched_files[0]
        try:
            project_root = self.project_manager.find_project_root(first_patch_file)
        except ValueError as e:
            return ErrorHandler.create_error_result(0, f"Failed to find project root: {e}", start_time)
        
        print(f"Project: {project_root.name}")
        print(f"Patches to apply: {len(patch_infos)}")
        print()
        
        # 1: Apply patches
        print(f"[1/4] Applying all {len(patch_infos)} patches...")
        stage1_log = {"patches": [], "applied": 0, "failed": 0}
        applied_patches = []
        
        for i, patch_info in enumerate(patch_infos, 1):
            file_name = pathlib.Path(patch_info.touched_files[0]).name
            print(f"   [{i}/{len(patch_infos)}] Applying patch {patch_info.patch_id} to {file_name}...", end=" ", flush=True)
            
            # Convert to absolute path
            actual_file_path = pathlib.Path(patch_info.touched_files[0])
            if not actual_file_path.is_absolute():
                autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
                actual_file_path = autosec_root / actual_file_path
            
            if not actual_file_path.exists():
                print(f"✗ File not found: {actual_file_path}")
                stage1_log["patches"].append({
                    "patch_id": patch_info.patch_id,
                    "file": str(actual_file_path),
                    "status": "error",
                    "error": "File not found",
                })
                stage1_log["failed"] += 1
                continue
            
            # Read original code before applying patch (for diff logging)
            original_code = actual_file_path.read_text(encoding='utf-8')
            
            # Apply patch via LLM
            patch_info_dict = {
                "file_path": str(actual_file_path),
                "unified_diff": patch_info.unified_diff,
                "plan": patch_info.plan,
                "safety_verification": patch_info.safety_verification
            }
            
            patch_result = self.patch_applicator.apply_patch(patch_info_dict)
            
            if patch_result["status"] != "success":
                print(f"✗ Failed: {patch_result.get('error', 'Unknown error')}")
                stage1_log["patches"].append({
                    "patch_id": patch_info.patch_id,
                    "file": str(actual_file_path),
                    "status": "error",
                    "error": patch_result.get("error", "Unknown error"),
                })
                stage1_log["failed"] += 1
                continue
            
            print("✓")
            stage1_log["applied"] += 1
            
            # Build patch log entry with LLM I/O
            patch_log_entry = {
                "patch_id": patch_info.patch_id,
                "file": str(actual_file_path),
                "status": "success",
                "model_used": patch_result.get("model_used", ""),
            }
            
            # Save LLM I/O to separate file for detailed inspection
            llm_io = patch_result.get("llm_io", {})
            if llm_io:
                llm_log_file = session_dir / f"llm_patch_{patch_info.patch_id:03d}.json"
                try:
                    with open(llm_log_file, 'w') as f:
                        json.dump(llm_io, f, indent=2)
                    patch_log_entry["llm_io_log"] = str(llm_log_file)
                except Exception as e:
                    patch_log_entry["llm_io_log_error"] = str(e)
            
            stage1_log["patches"].append(patch_log_entry)
            applied_patches.append({
                "patch_info": patch_info,
                "patch_result": patch_result,
                "file_path": actual_file_path,
                "original_code": original_code,
            })
        
        verification_log["stages"]["1_apply_patches"] = stage1_log
        
        if not applied_patches:
            print("✗ No patches were successfully applied")
            self._save_verification_log(verification_log, session_dir, start_time)
            return ErrorHandler.create_error_result(0, "Failed to apply any patches", start_time)
        
        print(f"✓ Successfully applied {len(applied_patches)}/{len(patch_infos)} patches\n")
        
        # 2: Check code diff (compare original vs patched)
        print(f"[2/4] Checking code changes...")
        stage2_log = {"diffs": []}
        
        for ap in applied_patches:
            file_path = ap["file_path"]
            original_code = ap["original_code"]
            patched_code = ap["patch_result"].get("patched_code", "")
            
            # Generate unified diff
            original_lines = original_code.splitlines(keepends=True)
            patched_lines = patched_code.splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                original_lines, patched_lines,
                fromfile=f"a/{file_path.name}",
                tofile=f"b/{file_path.name}",
            ))
            diff_text = "".join(diff_lines)
            
            added = sum(1 for l in diff_lines if l.startswith('+') and not l.startswith('+++'))
            removed = sum(1 for l in diff_lines if l.startswith('-') and not l.startswith('---'))
            
            print(f"   {file_path.name}: +{added} -{removed} lines changed")
            
            diff_entry = {
                "file": str(file_path),
                "lines_added": added,
                "lines_removed": removed,
            }
            
            # Save diff to file
            diff_file = session_dir / f"diff_patch_{ap['patch_info'].patch_id:03d}.diff"
            try:
                diff_file.write_text(diff_text, encoding='utf-8')
                diff_entry["diff_file"] = str(diff_file)
            except Exception as e:
                diff_entry["diff_file_error"] = str(e)
            
            stage2_log["diffs"].append(diff_entry)
        
        verification_log["stages"]["2_code_diff"] = stage2_log
        print(f"✓ Code diff logged\n")
        
        # 3: Build the project in Docker
        print(f"[3/4] Building project to verify patches compile...")
        build_result = self.build_runner.run_build_only(project_root, session_dir)
        
        # Collect Docker log paths
        build_artifacts_dir = session_dir / "build"
        docker_stdout_path = build_artifacts_dir / "docker_stdout.log"
        docker_stderr_path = build_artifacts_dir / "docker_stderr.log"
        
        stage3_log = {
            "success": build_result.get("success", False),
            "return_code": build_result.get("return_code"),
            "duration_seconds": build_result.get("duration", 0),
            "docker_image": build_result.get("docker_image", ""),
            "stack": build_result.get("stack", ""),
            "error": build_result.get("error"),
            "docker_logs": {
                "stdout": str(docker_stdout_path) if docker_stdout_path.exists() else None,
                "stderr": str(docker_stderr_path) if docker_stderr_path.exists() else None,
            },
        }
        verification_log["stages"]["3_build"] = stage3_log
        
        if not build_result.get("success"):
            print(f"✗ Build failed — patches broke compilation")
            
            # Log stderr snippet for quick debugging
            if docker_stderr_path.exists():
                stderr_content = docker_stderr_path.read_text(encoding='utf-8', errors='replace')
                last_lines = "\n".join(stderr_content.strip().splitlines()[-20:])
                print(f"\n--- Last 20 lines of Docker stderr ---")
                print(last_lines)
                print(f"--- Full log: {docker_stderr_path} ---\n")
            
            failure_result = VerificationResult(
                patch_id=0,
                status="REJECTED",
                build_success=False,
                test_success=False,
                reasoning=f"Build failed: {build_result.get('error', 'Unknown error')}",
                confidence_score=0.0,
                patcher_feedback={},
                verification_time=(datetime.datetime.now() - start_time).total_seconds()
            )
            
            verification_log["stages"]["4_tests"] = {"skipped": True, "reason": "Build failed"}
            self._save_verification_log(verification_log, session_dir, start_time, failure_result)
            return failure_result
        
        print(f"✓ Build succeeded — patches compile cleanly\n")
        
        # 4: Run all tests 
        print(f"[4/4] Running all tests (existing + POV)...")
        docker_image = build_result.get("docker_image")
        stack = build_result.get("stack")
        
        test_result = self.build_runner.run_tests_only(project_root, docker_image, stack, session_dir)
        
        # Collect test Docker log paths
        test_artifacts_dir = session_dir / "tests"
        test_stdout_path = test_artifacts_dir / "docker_stdout.log"
        test_stderr_path = test_artifacts_dir / "docker_stderr.log"
        
        test_success = test_result.get("status") == "PASS"
        test_exec = test_result.get("test_execution", {})
        test_results_data = test_exec.get("test_results", {})
        
        stage4_log = {
            "status": test_result.get("status"),
            "test_discovery": test_result.get("test_discovery", {}),
            "test_execution": test_exec,
            "docker_logs": {
                "stdout": str(test_stdout_path) if test_stdout_path.exists() else None,
                "stderr": str(test_stderr_path) if test_stderr_path.exists() else None,
            },
        }
        verification_log["stages"]["4_tests"] = stage4_log
        
        if test_success:
            status = "APPROVED"
            passed_count = test_results_data.get("passed_tests", 0)
            total_count = test_results_data.get("total_tests", 0)
            reasoning = f"✓ Build successful; ✓ All tests passed ({passed_count}/{total_count})"
            confidence = 0.9
            print(f"✓ All tests passed\n")
        else:
            status = "REJECTED"
            failed = test_results_data.get("failed_tests", 0)
            total = test_results_data.get("total_tests", 0)
            reasoning = f"✓ Build successful; ✗ Tests failed ({failed}/{total} failures)"
            confidence = 0.3
            print(f"✗ Tests failed ({failed}/{total} failures)")
            
            # Print failed test details
            failed_details = test_results_data.get("failed_test_details", [])
            if failed_details:
                print(f"\n--- Failed tests ---")
                for fd in failed_details[:10]:  # Show first 10
                    print(f"   {fd.get('test_name', '?')}: {fd.get('failure_message', '?')[:120]}")
                if len(failed_details) > 10:
                    print(f"   ... and {len(failed_details) - 10} more")
                print()
            
            # Log stderr snippet
            if test_stderr_path.exists():
                stderr_content = test_stderr_path.read_text(encoding='utf-8', errors='replace')
                last_lines = "\n".join(stderr_content.strip().splitlines()[-15:])
                print(f"--- Last 15 lines of test stderr ---")
                print(last_lines)
                print(f"--- Full log: {test_stderr_path} ---\n")
        
        verification_result = VerificationResult(
            patch_id=0,
            status=status,
            build_success=True,
            test_success=test_success,
            reasoning=reasoning,
            confidence_score=confidence,
            patcher_feedback={},
            verification_time=(datetime.datetime.now() - start_time).total_seconds()
        )
        
        self._save_verification_log(verification_log, session_dir, start_time, verification_result)
        
        print("="*80)
        print(f"VERIFICATION RESULT: {status}")
        print(f"Reasoning: {reasoning}")
        print(f"Logs: {session_dir}")
        print("="*80)
        
        return verification_result
    
    def _save_verification_log(
        self,
        verification_log: Dict[str, Any],
        session_dir: pathlib.Path,
        start_time: datetime.datetime,
        verification_result: Optional[VerificationResult] = None,
    ):
        """Save comprehensive verification log to session directory."""
        try:
            end_time = datetime.datetime.now()
            verification_log["end_time"] = end_time.isoformat()
            verification_log["total_duration_seconds"] = (end_time - start_time).total_seconds()
            
            if verification_result:
                verification_log["final_decision"] = {
                    "status": verification_result.status,
                    "reasoning": verification_result.reasoning,
                    "confidence": verification_result.confidence_score,
                    "build_success": verification_result.build_success,
                    "test_success": verification_result.test_success,
                    "verification_time": verification_result.verification_time,
                }
            
            results_file = session_dir / "verification_results.json"
            with open(results_file, 'w') as f:
                json.dump(verification_log, f, indent=2)
            
            print(f"📂 Results saved to: {session_dir}\n")
            
        except Exception as e:
            print(f"⚠️  Failed to save verification log: {e}")
    

def create_verifier(config: Optional[Dict[str, Any]] = None) -> VerifierCore:
    """Factory function to create a configured verifier instance"""
    return VerifierCore(config)