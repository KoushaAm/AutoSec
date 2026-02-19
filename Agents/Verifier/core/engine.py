import json
import pathlib
import datetime
import sys
import shutil
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
    
    def verify_fixer_output(self, fixer_json_path: str, pov_tests: Optional[List[Dict[str, Any]]] = None) -> List[VerificationResult]:
        """
        Apply patches → Build → Add tests → Run tests
        
        1. Apply all patches to Projects/Sources/<project>/
        2. Build the project (verify patches compile)
        3. Copy POV tests from Exploiter to Projects/Sources/<project>/
        4. Generate LLM tests next to vulnerable files in Projects/Sources/<project>/
        5. Run `mvn test` (Maven auto-compiles tests and runs them)
        6. Return simple pass/fail
        
        Args:
            fixer_json_path: Path to Patcher's output manifest
            pov_tests: POV tests from state['exploiter']['pov_tests'] (optional temp)
        """
        with open(fixer_json_path, 'r') as f:
            fixer_data = json.load(f)
        
        session_dir = self.artifact_manager.create_session_directory(fixer_json_path)
        
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
        
        # Verify all patches together
        result = self._verify_all_patches_simple(patch_infos, session_dir, pov_tests or [])
        
        # Save session results
        self.artifact_manager.save_session_summary([result], session_dir, fixer_json_path)
        
        return [result]
    
    def _verify_all_patches_simple(
        self, 
        patch_infos: List[PatchInfo], 
        session_dir: pathlib.Path,
        pov_tests: List[Dict[str, Any]]
    ) -> VerificationResult:
        """
        Simple verification: Apply patches → Build → Add tests → Run tests
        """
        start_time = datetime.datetime.now()
        
        print("="*80)
        print("VERIFICATION WORKFLOW")
        print("="*80)
        
        # Determine project root from first patch
        first_patch_file = patch_infos[0].touched_files[0]
        try:
            project_root = self.project_manager.find_project_root(first_patch_file)
        except ValueError as e:
            return ErrorHandler.create_error_result(0, f"Failed to find project root: {e}", start_time)
        
        print(f"Project: {project_root.name}")
        print(f"Patches to apply: {len(patch_infos)}")
        print(f"POV tests to add: {len(pov_tests)}")
        print()
        
        # STEP 1: Apply ALL patches
        print(f"[1/4] Applying all {len(patch_infos)} patches...")
        applied_patches = []
        for i, patch_info in enumerate(patch_infos, 1):
            print(f"   [{i}/{len(patch_infos)}] Applying patch {patch_info.patch_id} to {pathlib.Path(patch_info.touched_files[0]).name}...", end=" ", flush=True)
            
            # Convert to absolute path
            actual_file_path = pathlib.Path(patch_info.touched_files[0])
            if not actual_file_path.is_absolute():
                autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
                actual_file_path = autosec_root / actual_file_path
            
            if not actual_file_path.exists():
                print(f"✗ File not found: {actual_file_path}")
                continue
            
            # Apply patch
            patch_info_dict = {
                "file_path": str(actual_file_path),
                "unified_diff": patch_info.unified_diff,
                "plan": patch_info.plan,
                "safety_verification": patch_info.safety_verification
            }
            
            patch_result = self.patch_applicator.apply_patch(patch_info_dict)
            
            if patch_result["status"] != "success":
                print(f"✗ Failed: {patch_result.get('error', 'Unknown error')}")
                continue
            
            print("✓")
            applied_patches.append({
                "patch_info": patch_info,
                "patch_result": patch_result,
                "file_path": actual_file_path
            })
        
        if not applied_patches:
            print("✗ No patches were successfully applied")
            return ErrorHandler.create_error_result(0, "Failed to apply any patches", start_time)
        
        print(f"✓ Successfully applied {len(applied_patches)}/{len(patch_infos)} patches\n")
        
        # STEP 2: Build the project FIRST (verify patches compile)
        print(f"[2/4] Building project to verify patches compile...")
        build_result = self.build_runner.run_build_only(project_root, session_dir)
        
        if not build_result.get("success"):
            print(f"✗ Build failed - patches broke compilation\n")
            
            failure_result = VerificationResult(
                patch_id=0,
                status="REJECTED",
                build_success=False,
                test_success=False,
                reasoning=f"Build failed: {build_result.get('error', 'Unknown error')}",
                confidence_score=0.0,
                start_time=start_time,
                end_time=datetime.datetime.now(),
                verification_time=(datetime.datetime.now() - start_time).total_seconds()
            )
            
            self._save_simple_artifacts(applied_patches, session_dir, build_result, None, failure_result)
            return failure_result
        
        print(f"✓ Build succeeded - patches compile cleanly\n")
        
        # STEP 3: Now add POV tests (build succeeded, so safe to add tests)
        print(f"[3/4] Adding tests to project...")
        print(f"   Copying POV tests from Exploiter...")
        pov_copied = self._copy_pov_tests(project_root, pov_tests)
        print(f"   ✓ Copied {pov_copied} POV test(s)")
        
        print(f"   Generating LLM security tests...")
        llm_generated = self._generate_llm_tests(project_root, applied_patches[0]["patch_info"])
        print(f"   ✓ Generated {llm_generated} LLM test(s)\n")
        
        # STEP 4: Run ALL tests (Maven auto-compiles and runs tests)
        print(f"[4/4] Running all tests (existing + POV + LLM)...")
        docker_image = build_result.get("docker_image")
        stack = build_result.get("stack")
        
        test_result = self.build_runner.run_tests_only(project_root, docker_image, stack, session_dir)
        
        # Simple evaluation: did tests pass or fail?
        test_success = test_result.get("status") == "PASS"
        
        if test_success:
            status = "APPROVED"
            reasoning = "✓ Build successful; ✓ All tests passed (existing + POV + LLM)"
            confidence = 0.9
            print(f"✓ All tests passed\n")
        else:
            status = "REJECTED"
            test_exec = test_result.get("test_execution", {})
            test_results = test_exec.get("test_results", {})
            failed = test_results.get("failed_tests", 0)
            total = test_results.get("total_tests", 0)
            reasoning = f"✓ Build successful; ✗ Tests failed ({failed}/{total} failures)"
            confidence = 0.3
            print(f"✗ Tests failed ({failed}/{total} failures)\n")
        
        verification_result = VerificationResult(
            patch_id=0,
            status=status,
            build_success=True,
            test_success=test_success,
            reasoning=reasoning,
            confidence_score=confidence,
            start_time=start_time,
            end_time=datetime.datetime.now(),
            verification_time=(datetime.datetime.now() - start_time).total_seconds()
        )
        
        self._save_simple_artifacts(applied_patches, session_dir, build_result, test_result, verification_result)
        
        print("="*80)
        print(f"VERIFICATION RESULT: {status}")
        print(f"Reasoning: {reasoning}")
        print("="*80)
        
        return verification_result
    
    def _copy_pov_tests(self, project_root: pathlib.Path, pov_tests: List[Dict[str, Any]]) -> int:
        """
        Copy POV tests from Exploiter's output to the working project.
        
        Args:
            project_root: Root of the project in Projects/Sources/
            pov_tests: List of POV test info from state['exploiter']['pov_tests']
                       Each has 'pov_test_path' pointing to the test file location (relative path)
        
        Returns:
            Number of POV tests successfully copied
        """
        if not pov_tests:
            return 0
        
        copied = 0
        autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
        
        # Extract project name from project_root (e.g., "nahsra__antisamy_CVE-2016-10006_1.5.3")
        project_name = project_root.name
        
        # Hardcoded exploiter workdir path
        exploiter_workdir = autosec_root / "Agents" / "Exploiter" / "data" / "cwe-bench-java" / "workdir_no_branch" / "project-sources" / project_name
        
        for pov_test in pov_tests:
            pov_test_paths = pov_test.get("pov_test_path", [])
            if not pov_test_paths:
                continue
            
            # Use the first path provided (this is a relative path)
            relative_pov_path = pov_test_paths[0]
            
            # Construct the full absolute path in the Exploiter workdir
            source_path = exploiter_workdir / relative_pov_path
            
            if not source_path.exists():
                print(f"      Warning: POV test not found: {source_path}")
                continue
            
            # find target path (keep the same relative structure)
            # Example: If source is .../project-sources/<project>/src/test/java/Foo.java
            # Copy to Projects/Sources/<project>/src/test/java/Foo.java
            
            # Find 'src' in the source path
            try:
                parts = source_path.parts
                src_index = parts.index('src')
                relative_path = pathlib.Path(*parts[src_index:])
                target_path = project_root / relative_path
                
                # Create parent directories
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy the test file
                shutil.copy2(source_path, target_path)
                copied += 1
                print(f"      ✓ Copied {source_path.name} → {relative_path}")
                
            except (ValueError, IndexError):
                print(f"      Warning: Could not determine target path for {source_path}")
                continue
        
        return copied
    
    def _generate_llm_tests(self, project_root: pathlib.Path, patch_info: PatchInfo) -> int:
        """
        Generate LLM security tests and place them next to the vulnerable file.
        
        Args:
            project_root: Root of the project in Projects/Sources/
            patch_info: Patch information (contains vulnerable file and CWE info)
        
        Returns:
            Number of LLM tests successfully generated
        """
        try:
            # Import test generator
            from ..testing.llm.test_generator import TestGenerationClient
            
            test_generator = TestGenerationClient(verbose=True)
            
            # Get the vulnerable file
            vulnerable_file = pathlib.Path(patch_info.touched_files[0])
            if not vulnerable_file.is_absolute():
                autosec_root = pathlib.Path(__file__).parent.parent.parent.parent
                vulnerable_file = autosec_root / vulnerable_file
            
            if not vulnerable_file.exists():
                print(f"      Warning: Vulnerable file not found: {vulnerable_file}")
                return 0
            
            # Read the patched code
            patched_code = vulnerable_file.read_text(encoding='utf-8')
            
            # Extract CWE info
            cwe_id = patch_info.cwe_matches[0]['cwe_id'] if patch_info.cwe_matches else 'Unknown'
            vulnerability_desc = (
                patch_info.cwe_matches[0].get('description', 'Security vulnerability')
                if patch_info.cwe_matches else 'Security vulnerability'
            )
            
            # Generate tests
            print(f"      Generating tests for {vulnerable_file.name} (CWE-{cwe_id})...")
            generated_test_code = test_generator.generate_tests(
                patched_code=patched_code,
                cwe_id=cwe_id,
                vulnerability_description=vulnerability_desc,
                patch_plan=patch_info.plan,
                security_notes=patch_info.safety_verification,
                num_tests=3
            )
            
            if not generated_test_code:
                print(f"      Warning: Failed to generate LLM tests")
                return 0
            
            # Determine test file location
            # If vulnerable file is src/main/java/com/example/Foo.java
            # Test should go to src/test/java/com/example/FooSecurityTest.java
            
            parts = vulnerable_file.parts
            if 'src' in parts and 'main' in parts:
                src_index = parts.index('src')
                main_index = parts.index('main')
                
                # Replace 'main' with 'test'
                test_parts = list(parts[:main_index]) + ['test'] + list(parts[main_index + 1:])
                
                # Change filename to *SecurityTest.java
                base_name = vulnerable_file.stem
                test_parts[-1] = f"{base_name}SecurityTest.java"
                
                test_file_path = project_root / pathlib.Path(*test_parts[src_index:])
                
                # Create parent directories
                test_file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write test file
                test_file_path.write_text(generated_test_code, encoding='utf-8')
                
                print(f"      ✓ Generated {test_file_path.relative_to(project_root)}")
                return 1
            else:
                print(f"      Warning: Could not determine test file location for {vulnerable_file}")
                return 0
                
        except Exception as e:
            print(f"      Warning: LLM test generation failed: {e}")
            return 0
    
    def _save_simple_artifacts(
        self,
        applied_patches: List[Dict[str, Any]],
        session_dir: pathlib.Path,
        build_result: Dict[str, Any],
        test_result: Optional[Dict[str, Any]],
        verification_result: VerificationResult
    ):
        """Save simple verification artifacts"""
        try:
            results_file = session_dir / "verification_results.json"
            results_data = {
                "patches_applied": [
                    {
                        "patch_id": p["patch_info"].patch_id,
                        "file": str(p["file_path"]),
                        "status": p["patch_result"]["status"]
                    }
                    for p in applied_patches
                ],
                "build": {
                    "success": build_result.get("success", False),
                    "duration": build_result.get("duration", 0),
                    "docker_image": build_result.get("docker_image", ""),
                    "stack": build_result.get("stack", "")
                },
                "tests": test_result or {},
                "final_decision": {
                    "status": verification_result.status,
                    "reasoning": verification_result.reasoning,
                    "confidence": verification_result.confidence_score,
                    "verification_time": verification_result.verification_time,
                    "build_success": verification_result.build_success,
                    "test_success": verification_result.test_success
                }
            }
            
            with open(results_file, 'w') as f:
                json.dump(results_data, f, indent=2)
            
            print(f"📂 Results saved to: {session_dir}\n")
            
        except Exception as e:
            print(f"⚠️  Failed to save artifacts: {e}")


def create_verifier(config: Optional[Dict[str, Any]] = None) -> VerifierCore:
    """Factory function to create a configured verifier instance"""
    return VerifierCore(config)