import pathlib
import sys
from typing import Dict, Any, Optional

# Add paths for dependencies
VERIFIER_PATH = pathlib.Path(__file__).parent.parent

# Import Docker runner from core
from ..core.docker_runner import DockerRunner

# Import LLM test generation
from ..testing.llm.test_generator import TestGenerationClient

# Import models
from ..models.verification import PatchInfo


class LLMTestHandler:
    """Handles LLM-based test generation and execution"""
    
    def __init__(self, verbose: bool = True):
        self.verifier_path = VERIFIER_PATH
        self.test_generator = TestGenerationClient(verbose=verbose)
        self.docker_runner = None
    
    def generate_and_run_tests(
        self,
        project_path: pathlib.Path,
        docker_image: str,
        stack: str,
        patch_info: PatchInfo,
        artifacts_dir: pathlib.Path
    ) -> Dict[str, Any]:
        """
        Generate LLM tests and run them in Docker.
        
        Args:
            project_path: Path to patched project
            docker_image: Docker image to use (from successful build)
            stack: Build system (maven/gradle)
            patch_info: Patch information for test generation context
            artifacts_dir: Directory for test artifacts
            
        Returns:
            Dictionary with LLM test generation and execution results
        """
        result = {
            "status": "SKIP",
            "test_generation": {},
            "test_execution": {}
        }
        
        # Initialize Docker runner
        self.docker_runner = DockerRunner(cache_dir=artifacts_dir / "build-cache")
        
        try:
            print(f"      [LLM Tests] Generating tests with LLM...")
            
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
            test_file_path = self._write_generated_tests(
                project_path, 
                stack, 
                generated_test_code, 
                patch_info
            )
            
            result["test_generation"] = {
                "status": "SUCCESS",
                "test_file": str(test_file_path.relative_to(project_path)),
                "test_code_length": len(generated_test_code),
                "cwe_id": cwe_id
            }
            
            print(f"      ✓ Generated tests written to: {test_file_path.name}")
            
            # Run generated tests in Docker
            print(f"      [LLM Tests] Running generated tests in Docker...")
            test_result = self._run_generated_tests_in_docker(
                project_path,
                docker_image,
                stack,
                test_file_path,
                artifacts_dir
            )
            
            result["test_execution"] = test_result
            result["status"] = test_result.get("status", "UNKNOWN")
            
            if test_result.get("status") == "PASS":
                print(f"      ✓ LLM tests passed ({test_result['test_results']['passed_tests']}/{test_result['test_results']['total_tests']})")
            else:
                print(f"      ✗ LLM tests failed")
        
        except Exception as e:
            print(f"      ✗ LLM test generation/execution error: {e}")
            result["test_generation"] = {
                "status": "ERROR",
                "message": str(e)
            }
            result["status"] = "ERROR"
        
        return result
    
    def _write_generated_tests(
        self, 
        project_path: pathlib.Path, 
        stack: str, 
        test_code: str, 
        patch_info: PatchInfo
    ) -> pathlib.Path:
        """Write generated tests to the appropriate test directory with proper package structure"""
        
        # Determine base test directory
        if stack in ["maven", "gradle"]:
            test_base_dir = project_path / "src" / "test" / "java"
        else:
            test_base_dir = project_path / "test"
        
        # Extract package from original source file path (most reliable)
        original_file_path = pathlib.Path(patch_info.touched_files[0])
        package_path = self._extract_package_path(original_file_path)
        
        # Fallback: parse package from LLM-generated code
        if not package_path:
            package_from_code = self._extract_package_from_code(test_code)
            package_path = package_from_code.replace('.', '/') if package_from_code else None
        
        # Build full test directory path
        test_dir = test_base_dir / package_path if package_path else test_base_dir
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test file
        test_file_name = f"{original_file_path.stem}SecurityTest.java"
        test_file_path = test_dir / test_file_name
        
        # Write and return
        test_file_path.write_text(test_code, encoding='utf-8')
        return test_file_path
    
    def _extract_package_path(self, file_path: pathlib.Path) -> Optional[str]:
        """
        Extract package directory structure from source file path.
        
        Example:
            Projects/Sources/project/src/main/java/org/owasp/esapi/File.java
            -> "org/owasp/esapi"
        """
        file_str = str(file_path)
        
        # Look for common Java source patterns
        patterns = [
            'src/main/java/',
            'src/test/java/',
            '/java/src/',
            '/src/'
        ]
        
        for pattern in patterns:
            if pattern in file_str:
                # Split and get everything after the pattern
                parts = file_str.split(pattern)
                if len(parts) > 1:
                    # Get the part after pattern. remove filename
                    package_with_file = parts[-1]
                    # Remove the filename to get just package path
                    package_path = str(pathlib.Path(package_with_file).parent)
                    # return if it's not just "." (current dir)
                    if package_path and package_path != '.':
                        return package_path
        
        return None
    
    def _extract_package_from_code(self, test_code: str) -> Optional[str]:
        """
        Extract package declaration from generated test code.
        
        Example:
            "package org.owasp.esapi;" -> "org.owasp.esapi"
        """
        import re
        
        # Look for package declaration at the start of the file
        match = re.search(r'^\s*package\s+([\w.]+)\s*;', test_code, re.MULTILINE)
        if match:
            return match.group(1)
        
        return None
    
    def _run_generated_tests_in_docker(
        self,
        project_path: pathlib.Path,
        docker_image: str,
        stack: str,
        test_file_path: pathlib.Path,
        artifacts_dir: pathlib.Path
    ) -> Dict[str, Any]:
        """Run generated tests in Docker"""
        
        # Extract test class name from file
        test_class = self._extract_test_class_from_file(test_file_path, project_path)
        
        # Build test command
        if stack == "maven":
            test_cmd = f"mvn test -Dtest={test_class}"
        elif stack == "gradle":
            test_cmd = f"gradle test --tests {test_class}"
        else:
            return {
                "status": "ERROR",
                "message": f"Unsupported stack: {stack}",
                "test_results": {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0
                }
            }
        
        # Run in Docker
        try:
            return_code, duration = self.docker_runner.run_command(
                docker_image,
                test_cmd,
                project_path,
                artifacts_dir,
                timeout=600  # 10 minutes for LLM tests
            )
            
            # Parse test results (simplified for now)
            test_results = self._parse_test_results(project_path, stack, return_code)
            
            status = "PASS" if return_code == 0 and test_results["failed_tests"] == 0 else "FAIL"
            
            return {
                "status": status,
                "command": test_cmd,
                "return_code": return_code,
                "duration_seconds": round(duration, 2),
                "test_results": test_results
            }
        
        except Exception as e:
            return {
                "status": "ERROR",
                "message": str(e),
                "test_results": {
                    "total_tests": 0,
                    "passed_tests": 0,
                    "failed_tests": 0
                }
            }
    
    def _extract_test_class_from_file(
        self, 
        test_file_path: pathlib.Path, 
        project_path: pathlib.Path
    ) -> str:
        """Extract fully qualified test class name from file path"""
        
        # Get relative path from project root
        relative_path = test_file_path.relative_to(project_path)
        
        # Remove file extension
        path_str = str(relative_path).replace('.java', '')
        
        # Find the part after 'src/test/java/'
        if 'src/test/java/' in path_str:
            class_path = path_str.split('src/test/java/')[-1]
        elif 'src/main/java/' in path_str:
            class_path = path_str.split('src/main/java/')[-1]
        else:
            class_path = pathlib.Path(path_str).name
        
        # Convert to Java package notation
        fully_qualified_class = class_path.replace('/', '.').replace('\\', '.')
        
        return fully_qualified_class
    
    def _parse_test_results(self, project_path: pathlib.Path, stack: str, return_code: int) -> Dict[str, Any]:
        """Parse test results from JUnit XML reports"""
        import xml.etree.ElementTree as ET
        
        test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "test_success_rate": 0.0
        }
        
        # Maven/Gradle test report locations
        report_paths = {
            "maven": ["target/surefire-reports"],
            "gradle": ["build/test-results/test"],
            "javac": []
        }
        
        paths_to_check = report_paths.get(stack, [])
        
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
                
                except Exception as e:
                    continue
        
        # Calculate success rate
        if test_results["total_tests"] > 0:
            test_results["test_success_rate"] = test_results["passed_tests"] / test_results["total_tests"]
        
        return test_results
