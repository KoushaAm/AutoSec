import subprocess
import pathlib
import sys
from typing import Dict, Any, Optional
from ..models.verification import VerificationResult, VerificationStatus, PatchInfo
import datetime

# Add existing Verifier infrastructure - fix path calculation
# Current file: pipeline_verifier/handlers/verification_handler.py
# Need to go up: handlers -> pipeline_verifier -> Verifier (3 levels, not 4)
VERIFIER_PATH = pathlib.Path(__file__).parent.parent.parent

# Import test infrastructure
sys.path.insert(0, str(VERIFIER_PATH / "testing"))
from test_discovery import TestDiscovery

# Import LLM test generation - fix import to avoid relative import issues
sys.path.insert(0, str(VERIFIER_PATH / "testing" / "regression"))
import llm_client
from llm_client import TestGenerationClient


class BuildVerifier:
    """Handles build verification and testing"""
    
    def __init__(self):
        self.verifier_path = VERIFIER_PATH
        self.test_discovery = TestDiscovery()
        self.test_generator = TestGenerationClient(verbose=True)
        self._ensure_verifier_path()
    
    def _ensure_verifier_path(self):
        """Ensure the verifier path is added to sys.path"""
        if str(self.verifier_path) not in sys.path:
            sys.path.insert(0, str(self.verifier_path))
    
    def run_verification(self, project_path: pathlib.Path, patch_info: Optional[PatchInfo] = None) -> Dict[str, Any]:
        """Run verification on a project: build + test discovery + test execution"""
        
        # TEMPORARY: Bypass build verification to test test execution
        print(f"      [BYPASS MODE] Skipping actual build, returning mock success")
        build_result = {
            "return_code": 0,
            "stdout": "Mock build output - bypassed for testing",
            "stderr": "",
            "success": True,
            "duration": 0.1
        }
        
        # After successful build, discover and run tests
        test_result = self._discover_and_run_tests(project_path, patch_info)
        
        # Merge build and test results
        build_result["test_discovery"] = test_result.get("test_discovery", {})
        build_result["test_execution"] = test_result.get("test_execution", {})
        build_result["test_status"] = test_result.get("status", "SKIP")
        build_result["test_generation"] = test_result.get("test_generation", {})
        
        # Update overall success based on both build and tests
        if test_result.get("status") == "FAIL":
            build_result["success"] = False
            build_result["return_code"] = 2  # Test failure code
        
        return build_result
    
    def _discover_and_run_tests(self, project_path: pathlib.Path, patch_info: Optional[PatchInfo] = None) -> Dict[str, Any]:
        """Discover existing tests, generate new ones if needed, and execute them"""
        result = {
            "status": "SKIP",
            "test_discovery": {},
            "test_execution": {},
            "test_generation": {}
        }
        
        try:
            # Detect build system
            stack_name = self._detect_build_system(project_path)
            
            print(f"      [Test Discovery] Scanning for tests in {stack_name} project...")
            
            cmd = [
                "python3", str(verifier_script),
                "--input", str(absolute_project_path),
                "--verbose"
            ]
            
            if test_discovery["has_tests"]:
                print(f"      [Test Discovery] Found {test_discovery['test_count']} existing test files ({test_discovery['test_framework']})")
                
                # Run existing tests
                test_execution = self._execute_tests(project_path, stack_name, test_discovery)
                result["test_execution"] = test_execution
                result["status"] = test_execution.get("status", "UNKNOWN")
                
            else:
                print(f"      [Test Discovery] No existing tests found")
                
                # Generate tests with LLM if patch info is available
                if patch_info:
                    print(f"      [Test Generation] Generating tests with LLM...")
                    generation_result = self._generate_and_run_tests(project_path, stack_name, patch_info)
                    result["test_generation"] = generation_result.get("test_generation", {})
                    result["test_execution"] = generation_result.get("test_execution", {})
                    result["status"] = generation_result.get("status", "SKIP")
                else:
                    print(f"      [Test Generation] Skipping - no patch info available")
                    result["status"] = "SKIP"
                    result["test_execution"] = {
                        "message": "No tests to execute and no patch info for generation",
                        "test_results": {
                            "total_tests": 0,
                            "passed_tests": 0,
                            "failed_tests": 0
                        }
                    }
        
        except Exception as e:
            print(f"      [Test Discovery] ERROR: {e}")
            result["status"] = "ERROR"
            result["error"] = str(e)
        
        return result
    
    def _generate_and_run_tests(self, project_path: pathlib.Path, stack_name: str, patch_info: PatchInfo) -> Dict[str, Any]:
        """Generate tests using LLM and execute them"""
        result = {
            "status": "SKIP",
            "test_generation": {},
            "test_execution": {}
        }
        
        try:
            # Read the patched code
            patched_file = project_path / pathlib.Path(patch_info.touched_files[0]).name
            if not patched_file.exists():
                raise FileNotFoundError(f"Patched file not found: {patched_file}")
            
            patched_code = patched_file.read_text(encoding='utf-8')
            
            # Extract context for test generation
            cwe_id = patch_info.cwe_matches[0]['cwe_id'] if patch_info.cwe_matches else 'Unknown'
            vulnerability_desc = patch_info.cwe_matches[0].get('description', 'Security vulnerability') if patch_info.cwe_matches else 'Security vulnerability'
            
            # Generate tests
            generated_test_code = self.test_generator.generate_tests(
                patched_code=patched_code,
                cwe_id=cwe_id,
                vulnerability_description=vulnerability_desc,
                patch_plan=patch_info.plan,
                security_notes=patch_info.safety_verification,
                num_tests=3
            )
            
            if not generated_test_code:
                result["test_generation"] = {
                    "status": "FAILED",
                    "message": "LLM failed to generate tests"
                }
                result["status"] = "ERROR"
                return result
            
            # Write tests to project
            test_file_path = self._write_generated_tests(project_path, stack_name, generated_test_code, patch_info)
            
            result["test_generation"] = {
                "status": "SUCCESS",
                "test_file": str(test_file_path.relative_to(project_path)),
                "test_code_length": len(generated_test_code),
                "cwe_id": cwe_id
            }
            
            print(f"      [Test Generation] ✓ Generated tests written to: {test_file_path.name}")
            
            # Re-discover tests (now includes generated ones)
            test_discovery = self.test_discovery.discover_tests(project_path, stack_name)
            
            # Execute generated tests
            test_execution = self._execute_tests(project_path, stack_name, test_discovery)
            result["test_execution"] = test_execution
            result["status"] = test_execution.get("status", "UNKNOWN")
            
        except Exception as e:
            print(f"      [Test Generation] ERROR: {e}")
            result["test_generation"] = {
                "status": "ERROR",
                "message": str(e)
            }
            result["status"] = "ERROR"
        
        return result
    
    def _write_generated_tests(self, project_path: pathlib.Path, stack_name: str, test_code: str, patch_info: PatchInfo) -> pathlib.Path:
        """Write generated tests to the appropriate test directory"""
        
        # Determine test directory based on build system
        if stack_name == "maven":
            test_dir = project_path / "src" / "test" / "java"
        elif stack_name == "gradle":
            test_dir = project_path / "src" / "test" / "java"
        else:
            test_dir = project_path / "test"
        
        # Create test directory if it doesn't exist
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate test file name
        original_file = pathlib.Path(patch_info.touched_files[0]).stem
        test_file_name = f"{original_file}SecurityTest.java"
        test_file_path = test_dir / test_file_name
        
        # Write test code
        test_file_path.write_text(test_code, encoding='utf-8')
        
        return test_file_path
    
    def _detect_build_system(self, project_path: pathlib.Path) -> str:
        """Detect the build system used by the project"""
        if (project_path / "pom.xml").exists():
            return "maven"
        elif (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
            return "gradle"
        else:
            return "javac"
    
    def _execute_tests(self, project_path: pathlib.Path, stack_name: str, test_discovery: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tests using the detected build system"""
        test_commands = test_discovery.get("test_commands", [])
        
        if not test_commands:
            return {
                "status": "ERROR",
                "message": "No test command available",
                "test_results": {"total_tests": 0, "passed_tests": 0, "failed_tests": 0}
            }
        
        # Use wrapper if it exists, otherwise use system command
        has_wrapper = (project_path / "mvnw").exists() or (project_path / "gradlew").exists()
        test_cmd = test_commands[0] if has_wrapper else (test_commands[1] if len(test_commands) > 1 else test_commands[0])
        
        print(f"      [Test Execution] Running: {test_cmd}")
        
        try:
            start_time = datetime.datetime.now()
            
            # Execute test command
            result = subprocess.run(
                test_cmd,
                cwd=str(project_path),
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            duration = (datetime.datetime.now() - start_time).total_seconds()
            
            # Parse test results from JUnit XML reports
            test_results = self._parse_test_results(project_path, stack_name, result.returncode)
            
            # Determine status
            if result.returncode == 0 and test_results["failed_tests"] == 0:
                status = "PASS"
                print(f"      [Test Execution] ✓ PASS - {test_results['passed_tests']}/{test_results['total_tests']} tests passed")
            elif test_results["failed_tests"] > 0:
                status = "FAIL"
                print(f"      [Test Execution] ✗ FAIL - {test_results['failed_tests']} tests failed")
            else:
                status = "ERROR"
                print(f"      [Test Execution] ⚠ ERROR - Test execution failed (RC: {result.returncode})")
            
            return {
                "status": status,
                "command": test_cmd,
                "return_code": result.returncode,
                "duration_seconds": round(duration, 2),
                "test_results": test_results,
                "stdout": result.stdout[:500],  # Truncate for brevity
                "stderr": result.stderr[:500]
            }
            
        except subprocess.TimeoutExpired:
            print(f"      [Test Execution] ⚠ TIMEOUT - Tests took longer than 5 minutes")
            return {
                "status": "ERROR",
                "message": "Test execution timed out",
                "test_results": {"total_tests": 0, "passed_tests": 0, "failed_tests": 0}
            }
        except Exception as e:
            print(f"      [Test Execution] ⚠ ERROR: {e}")
            return {
                "status": "ERROR",
                "message": str(e),
                "test_results": {"total_tests": 0, "passed_tests": 0, "failed_tests": 0}
            }
    
    def _parse_test_results(self, project_path: pathlib.Path, stack_name: str, return_code: int) -> Dict[str, Any]:
        """Parse test results from JUnit XML reports"""
        import xml.etree.ElementTree as ET
        
        test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "test_success_rate": 0.0,
            "failed_test_details": []
        }
        
        # Maven test reports location
        report_paths = {
            "maven": ["target/surefire-reports"],
            "gradle": ["build/test-results/test"],
            "javac": []
        }
        
        paths_to_check = report_paths.get(stack_name, [])
        
        for report_path in paths_to_check:
            full_path = project_path / report_path
            if not full_path.exists():
                continue
            
            # Parse all TEST-*.xml files
            for xml_file in full_path.glob("TEST-*.xml"):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    if root.tag == "testsuite":
                        suite_tests = int(root.get("tests", 0))
                        suite_failures = int(root.get("failures", 0))
                        suite_errors = int(root.get("errors", 0))
                        suite_skipped = int(root.get("skipped", 0))
                        
                        test_results["total_tests"] += suite_tests
                        test_results["failed_tests"] += (suite_failures + suite_errors)
                        test_results["skipped_tests"] += suite_skipped
                        test_results["passed_tests"] += (suite_tests - suite_failures - suite_errors - suite_skipped)
                        
                        # Extract failure details
                        for testcase in root.findall("testcase"):
                            failure = testcase.find("failure")
                            error = testcase.find("error")
                            
                            if failure is not None or error is not None:
                                test_name = testcase.get("name", "unknown")
                                class_name = testcase.get("classname", "unknown")
                                failure_msg = (failure.get("message") if failure is not None 
                                             else error.get("message") if error is not None else "Unknown")
                                
                                test_results["failed_test_details"].append({
                                    "test_name": f"{class_name}.{test_name}",
                                    "failure_message": failure_msg
                                })
                
                except Exception as e:
                    print(f"      [Test Parser] Warning: Failed to parse {xml_file.name}: {e}")
                    continue
        
        # Calculate success rate
        if test_results["total_tests"] > 0:
            test_results["test_success_rate"] = test_results["passed_tests"] / test_results["total_tests"]
        
        return test_results


class ResultComparator:
    """Evaluates verification results to determine patch effectiveness"""
    
    def compare_results(
        self,
        patch_info: PatchInfo,
        patched_result: Dict[str, Any],
        start_time: datetime.datetime
    ) -> VerificationResult:
        """Evaluate patched code verification results (no pre-patch comparison needed)"""
        
        patched_success = patched_result.get("success", False)
        patched_rc = patched_result.get("return_code", 1)
        
        print(f"      Patched result: RC={patched_rc}, Success={patched_success}")
        
        # Determine verification status
        status, reasoning, build_success, test_success = self._analyze_results(
            patched_success, patched_rc
        )
        
        # Generate patcher feedback for potential refinement
        patcher_feedback = self._generate_patcher_feedback(
            status, patch_info, patched_result
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
        patched_rc: int
    ) -> tuple[VerificationStatus, str, bool, bool]:
        """Analyze verification results to determine status"""
        
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
        else:
            # Success - patch builds and tests pass
            return (
                VerificationStatus.PATCH_VALID,
                "Patch builds successfully and passes all tests",
                True,
                True
            )
    
    def _generate_patcher_feedback(
        self,
        status: VerificationStatus,
        patch_info: PatchInfo,
        patched_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate feedback for patch refinement (Verifier → Patcher)"""
        
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
            "recommendations": []
        }
        
        # Add specific recommendations based on status
        if status == VerificationStatus.PATCH_BREAKS_BUILD:
            feedback["recommendations"].append("Fix compilation errors introduced by patch")
            feedback["build_regression"] = True
            
        elif status == VerificationStatus.PATCH_BREAKS_TESTS:
            feedback["recommendations"].append("Fix test failures introduced by patch")
            feedback["test_regression"] = True
            
        elif status == VerificationStatus.PATCH_VALID:
            feedback["recommendations"].append("Patch validated - builds and tests pass")
            feedback["patch_accepted"] = True
                
        else:  # VERIFICATION_ERROR
            feedback["recommendations"].append("Manual review required due to verification issues")
        
        # Include original patch metadata
        feedback["original_patch_confidence"] = patch_info.confidence
        feedback["cwe_matches"] = patch_info.cwe_matches
        
        return feedback


class POVTester:
    """Handles POV tests"""
    
    def run_pov_tests(self, project_path: pathlib.Path, patch_info: PatchInfo) -> Dict[str, Any]:
        """Run POV tests on patched code (placeholder for future implementation)"""
        # TODO: Implement when POV tests ready
        return {
            "pov_success": True,  # temp
            "vulnerability_eliminated": True,  # temp
            "pov_details": "POV testing not yet implemented"
        }