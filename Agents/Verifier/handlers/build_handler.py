import pathlib
import sys
from typing import Dict, Any, Optional
from ..models.verification import PatchInfo

# Add paths for dependencies
VERIFIER_PATH = pathlib.Path(__file__).parent.parent

# Import Docker runner from core (unified location)
from ..core.docker_runner import DockerRunner, check_docker
from ..core.project_detector import detect_java_project

# Import test discovery
from ..testing.test_discovery import TestDiscovery


class DockerBuildRunner:
    """Handles build verification and testing using Docker"""
    
    def __init__(self):
        self.verifier_path = VERIFIER_PATH
        self.test_discovery = TestDiscovery()
        self.docker_runner = None
        self._ensure_verifier_path()
    
    def _ensure_verifier_path(self):
        """Ensure the verifier path is added to sys.path"""
        if str(self.verifier_path) not in sys.path:
            sys.path.insert(0, str(self.verifier_path))
    
    def run_verification(self, project_path: pathlib.Path, patch_info: Optional[PatchInfo] = None, 
                        output_dir: Optional[pathlib.Path] = None) -> Dict[str, Any]:
        """
        Run verification on a project: build + test discovery + test execution in Docker
        
        Args:
            project_path: Path to the project in Projects/Sources/
            patch_info: Optional patch information
            output_dir: Directory to save build/test artifacts (under Verifier/output/)
        
        Returns:
            Dictionary with build and test results
        """
        # Check Docker availability
        if not check_docker():
            return {
                "success": False,
                "error": "Docker is not available or not running",
                "return_code": 2,
                "duration": 0
            }
        
        # Use provided output directory or create one under Verifier/output
        if output_dir:
            artifacts_dir = output_dir / "build_and_test"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Fallback to old location if no output_dir provided
            artifacts_dir = project_path.parent / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        self.docker_runner = DockerRunner(cache_dir=artifacts_dir / "build-cache")
        
        # Phase 1: Detect project type and get build commands
        print(f"      [1/3] Detecting project type...")
        stack, build_cmd, test_cmd, metadata = detect_java_project(project_path)
        
        if not build_cmd:
            error_msg = metadata.get('error', 'Unknown detection error')
            print(f"      ✗ Detection failed: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "return_code": 2,
                "duration": 0
            }
        
        print(f"      ✓ Detected {stack} project")
        
        # Phase 2: Build in Docker with retry
        print(f"      [2/3] Building in Docker...")
        project_id = project_path.name.lower().replace(" ", "-")
        
        build_result = self.docker_runner.build_with_retry(
            stack=stack,
            build_cmd=build_cmd,
            worktree=project_path,
            artifacts=artifacts_dir,
            timeout=1800,  # 30 minutes
            project_identifier=project_id,
            verbose=False
        )
        
        if not build_result["success"]:
            print(f"      ✗ Build failed")
            return {
                "success": False,
                "error": f"Build failed: {build_result.get('error', 'Unknown')}",
                "return_code": build_result["return_code"],
                "duration": build_result["duration"],
                "build_result": build_result
            }
        
        print(f"      ✓ Build passed (using {build_result['image_used']})")
        
        # Phase 3: Run existing tests in Docker
        print(f"      [3/3] Running tests in Docker...")
        test_result = self._run_tests_in_docker(
            project_path, 
            stack, 
            build_result["image_used"],
            artifacts_dir,
            patch_info
        )
        
        # Merge results
        final_result = {
            "success": build_result["success"] and test_result.get("status") != "FAIL",
            "return_code": 0 if test_result.get("status") == "PASS" else 1,
            "duration": build_result["duration"] + test_result.get("duration", 0),
            "build_result": build_result,
            "test_discovery": test_result.get("test_discovery", {}),
            "test_execution": test_result.get("test_execution", {}),
            "docker_image": build_result["image_used"],
            "stack": stack
        }
        
        return final_result
    
    def _run_tests_in_docker(
        self, 
        project_path: pathlib.Path,
        stack: str,
        docker_image: str,
        artifacts_dir: pathlib.Path,
        patch_info: Optional[PatchInfo] = None
    ) -> Dict[str, Any]:
        """Run tests in Docker container"""
        result = {
            "status": "SKIP",
            "duration": 0,
            "test_discovery": {},
            "test_execution": {}
        }
        
        try:
            # Discover tests
            test_discovery = self.test_discovery.discover_tests(project_path, stack)
            result["test_discovery"] = test_discovery
            
            if test_discovery["has_tests"]:
                print(f"      Found {test_discovery['test_count']} existing tests")
                
                # Get test command
                test_commands = test_discovery.get("test_commands", [])
                has_wrapper = (project_path / "mvnw").exists() or (project_path / "gradlew").exists()
                test_cmd = test_commands[0] if has_wrapper else (test_commands[1] if len(test_commands) > 1 else test_commands[0])
                
                # Run tests in Docker
                test_rc, test_duration = self.docker_runner.run_command(
                    docker_image,
                    test_cmd,
                    project_path,
                    artifacts_dir,
                    timeout=1200  # 20 minutes
                )
                
                # Parse test results
                test_results = self._parse_test_results(project_path, stack, test_rc)
                
                status = "PASS" if test_rc == 0 and test_results["failed_tests"] == 0 else "FAIL"
                
                result["test_execution"] = {
                    "status": status,
                    "command": test_cmd,
                    "return_code": test_rc,
                    "duration_seconds": round(test_duration, 2),
                    "test_results": test_results
                }
                result["status"] = status
                result["duration"] = test_duration
                
                if status == "PASS":
                    print(f"      ✓ Tests passed ({test_results['passed_tests']}/{test_results['total_tests']})")
                else:
                    print(f"      ✗ Tests failed ({test_results['failed_tests']} failures)")
            else:
                print(f"      No existing tests found")
                result["status"] = "SKIP"
                result["test_execution"] = {
                    "status": "SKIP",
                    "message": "No tests to execute",
                    "test_results": {
                        "total_tests": 0,
                        "passed_tests": 0,
                        "failed_tests": 0
                    }
                }
        
        except Exception as e:
            print(f"      ✗ Test execution error: {e}")
            result["status"] = "ERROR"
            result["error"] = str(e)
        
        return result
    
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

    def run_build_only(self, project_path: pathlib.Path, output_dir: pathlib.Path) -> Dict[str, Any]:
        """
        Run ONLY the build step (no tests).
        
        Args:
            project_path: Path to the project in Projects/Sources/
            output_dir: Directory to save build artifacts
        
        Returns:
            Dictionary with build results and docker image info
        """
        # Check Docker availability
        if not check_docker():
            return {
                "success": False,
                "error": "Docker is not available or not running",
                "return_code": 2,
                "duration": 0
            }
        
        artifacts_dir = output_dir / "build"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        self.docker_runner = DockerRunner(cache_dir=artifacts_dir / "build-cache")
        
        # Detect project type
        stack, build_cmd, test_cmd, metadata = detect_java_project(project_path)
        
        if not build_cmd:
            error_msg = metadata.get('error', 'Unknown detection error')
            return {
                "success": False,
                "error": error_msg,
                "return_code": 2,
                "duration": 0
            }
        
        # Build in Docker
        project_id = project_path.name.lower().replace(" ", "-")
        
        build_result = self.docker_runner.build_with_retry(
            stack=stack,
            build_cmd=build_cmd,
            worktree=project_path,
            artifacts=artifacts_dir,
            timeout=1800,  # 30 minutes
            project_identifier=project_id,
            verbose=False
        )
        
        # Return build result with stack info
        return {
            "success": build_result["success"],
            "error": build_result.get("error"),
            "return_code": build_result["return_code"],
            "duration": build_result["duration"],
            "docker_image": build_result.get("image_used"),
            "stack": stack
        }
    
    def run_tests_only(
        self, 
        project_path: pathlib.Path,
        docker_image: str,
        stack: str,
        output_dir: pathlib.Path
    ) -> Dict[str, Any]:
        """
        Run ONLY the tests (assumes project is already built).
        
        Args:
            project_path: Path to the project
            docker_image: Docker image to use (from build step)
            stack: Build system (maven/gradle)
            output_dir: Directory to save test artifacts
        
        Returns:
            Dictionary with test results
        """
        artifacts_dir = output_dir / "tests"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.docker_runner:
            self.docker_runner = DockerRunner(cache_dir=artifacts_dir / "build-cache")
        
        result = {
            "status": "SKIP",
            "duration": 0,
            "test_discovery": {},
            "test_execution": {}
        }
        
        try:
            # Discover tests
            test_discovery = self.test_discovery.discover_tests(project_path, stack)
            result["test_discovery"] = test_discovery
            
            if test_discovery["has_tests"]:
                # Get test command
                test_commands = test_discovery.get("test_commands", [])
                has_wrapper = (project_path / "mvnw").exists() or (project_path / "gradlew").exists()
                test_cmd = test_commands[0] if has_wrapper else (test_commands[1] if len(test_commands) > 1 else test_commands[0])
                
                # Run tests in Docker
                test_rc, test_duration = self.docker_runner.run_command(
                    docker_image,
                    test_cmd,
                    project_path,
                    artifacts_dir,
                    timeout=1200  # 20 minutes
                )
                
                # Parse test results
                test_results = self._parse_test_results(project_path, stack, test_rc)
                
                status = "PASS" if test_rc == 0 and test_results["failed_tests"] == 0 else "FAIL"
                
                result["test_execution"] = {
                    "status": status,
                    "command": test_cmd,
                    "return_code": test_rc,
                    "duration_seconds": round(test_duration, 2),
                    "test_results": test_results
                }
                result["status"] = status
                result["duration"] = test_duration
            else:
                result["status"] = "SKIP"
                result["test_execution"] = {
                    "status": "SKIP",
                    "message": "No tests to execute",
                    "test_results": {
                        "total_tests": 0,
                        "passed_tests": 0,
                        "failed_tests": 0
                    }
                }
        
        except Exception as e:
            result["status"] = "ERROR"
            result["error"] = str(e)
        
        return result
