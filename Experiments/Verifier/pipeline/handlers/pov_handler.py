"""
POV Test Handler

Executes POV tests from the Exploiter agent.
Tests are run in Docker to verify that the patch actually fixes the vulnerability.
"""
import pathlib
import sys
import time
from typing import Dict, Any, List

# Add paths for dependencies
VERIFIER_PATH = pathlib.Path(__file__).parent.parent.parent

# Import Docker runner from core
sys.path.insert(0, str(VERIFIER_PATH / "core"))
from docker_runner import DockerRunner


class POVTestRunner:
    """Handles POV (Proof of Vulnerability) tests from Exploiter"""
    
    def __init__(self):
        self.verifier_path = VERIFIER_PATH
        sys.path.insert(0, str(self.verifier_path / "core"))
        from docker_runner import DockerRunner
        self.docker_runner_class = DockerRunner
    
    def run_pov_tests(
        self, 
        project_path: pathlib.Path, 
        docker_image: str,
        stack: str,
        pov_tests: List[Dict[str, Any]],
        artifacts_dir: pathlib.Path
    ) -> Dict[str, Any]:
        """
        Run POV tests from Exploiter on the patched project.
        
        Args:
            project_path: Path to patched project
            docker_image: Docker image to use (from successful build)
            stack: Build system (maven/gradle)
            pov_tests: List of POV test information from Exploiter
            artifacts_dir: Directory for test artifacts
            
        Returns:
            Dictionary with POV test results
        """
        if not pov_tests:
            return {
                "status": "SKIP",
                "message": "No POV tests provided",
                "total_pov_tests": 0,
                "passed_pov_tests": 0,
                "failed_pov_tests": 0
            }
        
        print(f"      [POV Tests] Running {len(pov_tests)} POV test(s) from Exploiter...")
        
        result = {
            "status": "UNKNOWN",
            "total_pov_tests": len(pov_tests),
            "passed_pov_tests": 0,
            "failed_pov_tests": 0,
            "pov_test_details": []
        }
        
        # Initialize Docker runner
        docker_runner = self.docker_runner_class(cache_dir=artifacts_dir / "build-cache")
        
        try:
            # For each POV test, check if it exists in the project
            for idx, pov_test in enumerate(pov_tests, start=1):
                pov_test_paths = pov_test.get("pov_test_path", [])
                
                if not pov_test_paths:
                    print(f"      POV Test {idx}: No test path provided")
                    result["pov_test_details"].append({
                        "test_index": idx,
                        "status": "SKIP",
                        "reason": "No test path provided"
                    })
                    continue
                
                # Use first test path
                pov_test_relative_path = pov_test_paths[0]
                pov_test_full_path = project_path / pov_test_relative_path
                
                if not pov_test_full_path.exists():
                    print(f"      POV Test {idx}: Test file not found: {pov_test_relative_path}")
                    result["pov_test_details"].append({
                        "test_index": idx,
                        "test_path": pov_test_relative_path,
                        "status": "SKIP",
                        "reason": "Test file not found in patched project"
                    })
                    continue
                
                # Extract test class name from path
                test_class = self._extract_test_class_name(pov_test_relative_path)
                
                # Run specific POV test
                print(f"      POV Test {idx}: Running {test_class}...")
                test_result = self._run_single_pov_test(
                    project_path,
                    docker_runner,
                    docker_image,
                    stack,
                    test_class,
                    artifacts_dir
                )
                
                result["pov_test_details"].append({
                    "test_index": idx,
                    "test_path": pov_test_relative_path,
                    "test_class": test_class,
                    "vulnerability": pov_test.get("vulnerability", "Unknown"),
                    "status": test_result["status"],
                    "return_code": test_result["return_code"],
                    "duration_seconds": test_result["duration_seconds"]
                })
                
                if test_result["status"] == "PASS":
                    result["passed_pov_tests"] += 1
                    print(f"      ✓ POV Test {idx} passed (vulnerability eliminated)")
                else:
                    result["failed_pov_tests"] += 1
                    print(f"      ✗ POV Test {idx} failed (vulnerability still present!)")
            
            # Determine overall POV status
            if result["failed_pov_tests"] > 0:
                result["status"] = "FAIL"
                result["message"] = f"{result['failed_pov_tests']} POV test(s) failed - vulnerability still exploitable"
            elif result["passed_pov_tests"] > 0:
                result["status"] = "PASS"
                result["message"] = f"All {result['passed_pov_tests']} POV test(s) passed - vulnerability eliminated"
            else:
                result["status"] = "SKIP"
                result["message"] = "No POV tests could be executed"
        
        except Exception as e:
            print(f"      ✗ POV test execution error: {e}")
            result["status"] = "ERROR"
            result["error"] = str(e)
        
        return result
    
    def _extract_test_class_name(self, test_path: str) -> str:
        """
        Extract the fully qualified test class name from a file path.
        
        Example:
            src/test/java/org/owasp/esapi/reference/PathTraversalTest.java
            -> org.owasp.esapi.reference.PathTraversalTest
        """
        # Remove file extension
        path_without_ext = test_path.replace('.java', '')
        
        # Find the part after 'src/test/java/' or 'src/main/java/'
        if 'src/test/java/' in path_without_ext:
            class_path = path_without_ext.split('src/test/java/')[-1]
        elif 'src/main/java/' in path_without_ext:
            class_path = path_without_ext.split('src/main/java/')[-1]
        else:
            # Fallback: just use the filename without directory
            class_path = pathlib.Path(path_without_ext).name
        
        # Convert path separators to dots for Java package notation
        fully_qualified_class = class_path.replace('/', '.')
        
        return fully_qualified_class
    
    def _run_single_pov_test(
        self,
        project_path: pathlib.Path,
        docker_runner: DockerRunner,
        docker_image: str,
        stack: str,
        test_class: str,
        artifacts_dir: pathlib.Path
    ) -> Dict[str, Any]:
        """Run a single POV test class"""
        
        # Build test command based on stack
        if stack == "maven":
            # Maven: run specific test class
            test_cmd = f"mvn test -Dtest={test_class}"
        elif stack == "gradle":
            # Gradle: run specific test class
            test_cmd = f"gradle test --tests {test_class}"
        else:
            return {
                "status": "ERROR",
                "return_code": -1,
                "duration_seconds": 0,
                "error": f"Unsupported stack for POV testing: {stack}"
            }
        
        # Run in Docker
        start_time = time.time()
        
        try:
            return_code, duration = docker_runner.run_command(
                docker_image,
                test_cmd,
                project_path,
                artifacts_dir,
                timeout=300  # 5 minutes per POV test
            )
            
            # POV test interpretation:
            # - Return code 0: Test passed (vulnerability is fixed!)
            # - Return code != 0: Test failed (vulnerability still exists)
            status = "PASS" if return_code == 0 else "FAIL"
            
            return {
                "status": status,
                "return_code": return_code,
                "duration_seconds": round(duration, 2),
                "command": test_cmd
            }
        
        except Exception as e:
            return {
                "status": "ERROR",
                "return_code": -1,
                "duration_seconds": round(time.time() - start_time, 2),
                "error": str(e)
            }
