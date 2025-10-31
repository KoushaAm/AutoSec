#!/usr/bin/env python3
"""
Test Execution and result parsing module

Handles execution of tests (existing or generated) and parsing of test results
from various build systems (Maven, Gradle).
"""
import pathlib
import datetime
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Tuple, Callable

from .test_discovery import TestDiscovery
from .smoke_generator import SmokeTestGenerator


class TestResultParser:
    """parse test execution results from build system output files"""
    
    def parse_test_results(self, project_path: pathlib.Path, stack_name: str, test_rc: int) -> Dict[str, Any]:
        """
        Args:
            project_path: Path to the project root
            stack_name: Build stack type (maven, gradle, javac)
            test_rc: Test execution return code
            
        Returns:
            Dictionary with parsed test results
        """
        test_results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "test_success_rate": 0.0,
            "failed_test_details": [],
            "test_reports_found": False,
            "test_execution_time": 0.0
        }
        
        report_paths = {
            "maven": [
                "target/surefire-reports",
                "target/failsafe-reports"
            ],
            "gradle": [
                "build/test-results/test",
                "build/test-results/integrationTest",
                "build/reports/tests/test"
            ]
        }
        
        paths_to_check = report_paths.get(stack_name, [])
        
        for report_path in paths_to_check:
            full_report_path = project_path / report_path
            if full_report_path.exists():
                test_results["test_reports_found"] = True
                
                if stack_name == "maven":
                    maven_results = self._parse_maven_test_reports(full_report_path)
                    self._merge_test_results(test_results, maven_results)
                elif stack_name == "gradle":
                    gradle_results = self._parse_gradle_test_reports(full_report_path)
                    self._merge_test_results(test_results, gradle_results)
        
        if test_results["total_tests"] > 0:
            test_results["test_success_rate"] = test_results["passed_tests"] / test_results["total_tests"]
        
        return test_results
    
    def _parse_maven_test_reports(self, report_dir: pathlib.Path) -> Dict[str, Any]:
        """parse Maven Surefire/Failsafe test report XML files."""
        results = {
            "total_tests": 0,
            "passed_tests": 0, 
            "failed_tests": 0,
            "skipped_tests": 0,
            "failed_test_details": [],
            "test_execution_time": 0.0
        }
        
        xml_files = list(report_dir.glob("TEST-*.xml"))
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                if root.tag == "testsuite":
                    suite_tests = int(root.get("tests", 0))
                    suite_failures = int(root.get("failures", 0))
                    suite_errors = int(root.get("errors", 0))
                    suite_skipped = int(root.get("skipped", 0))
                    suite_time = float(root.get("time", 0.0))
                    
                    results["total_tests"] += suite_tests
                    results["failed_tests"] += (suite_failures + suite_errors)
                    results["skipped_tests"] += suite_skipped
                    results["passed_tests"] += (suite_tests - suite_failures - suite_errors - suite_skipped)
                    results["test_execution_time"] += suite_time
                    
                    # Extract failure details
                    for testcase in root.findall("testcase"):
                        failure = testcase.find("failure")
                        error = testcase.find("error")
                        
                        if failure is not None or error is not None:
                            test_name = testcase.get("name", "unknown")
                            class_name = testcase.get("classname", "unknown")
                            failure_msg = (failure.get("message") if failure is not None 
                                         else error.get("message") if error is not None else "Unknown failure")
                            
                            results["failed_test_details"].append({
                                "test_name": f"{class_name}.{test_name}",
                                "failure_message": failure_msg
                            })
                            
            except Exception:
                continue
        
        return results
    
    def _parse_gradle_test_reports(self, report_dir: pathlib.Path) -> Dict[str, Any]:
        """parse Gradle test report XML files (similar to Maven format)."""
        # Gradle uses similar XML format to Maven
        return self._parse_maven_test_reports(report_dir)
    
    def _merge_test_results(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge test results from multiple sources."""
        target["total_tests"] += source["total_tests"]
        target["passed_tests"] += source["passed_tests"] 
        target["failed_tests"] += source["failed_tests"]
        target["skipped_tests"] += source["skipped_tests"]
        target["test_execution_time"] += source["test_execution_time"]
        target["failed_test_details"].extend(source["failed_test_details"])


class TestExecutor:
    """handling execution of tests and coordination between discovery, generation, and execution."""
    
    def __init__(self):
        self.test_discovery = TestDiscovery()
        self.smoke_generator = SmokeTestGenerator()
        self.result_parser = TestResultParser()
    
    def execute_behavior_validation(
        self,
        project_path: pathlib.Path, 
        artifacts_path: pathlib.Path,
        stack_name: str, 
        docker_image: str, 
        has_wrapper: bool,
        docker_runner_func: Callable,
        timeout: int = 1200, 
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        execute complete behavior validation pipeline
        
        Includes test discovery, execution of existing tests, or generation
        and execution of smoke tests if no tests are found.
        """
        behavior_result = {
            "status": "UNKNOWN",
            "check_name": "behavior_validation", 
            "start_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "end_time": None,
            "total_duration_seconds": 0,
            "test_discovery": {},
            "test_execution": {},
            "recommendations": []
        }
        
        behavior_start = time.time()
        
        try:
            # Phase 1: Test Discovery
            test_discovery = self.test_discovery.discover_tests(project_path, stack_name)
            behavior_result["test_discovery"] = test_discovery
            
            if verbose:
                if test_discovery["has_tests"]:
                    print(f"Tests: Found {test_discovery['test_count']} {test_discovery['test_framework']} test files")
                else:
                    print("Tests: No tests discovered")
            
            if test_discovery["has_tests"]:
                # Phase 2A: Execute existing tests
                behavior_result.update(self._execute_existing_tests(
                    project_path, artifacts_path, test_discovery, 
                    docker_image, has_wrapper, docker_runner_func, timeout, verbose
                ))
            else:
                # Phase 2B: Generate and execute smoke tests
                behavior_result.update(self._execute_smoke_tests(
                    project_path, artifacts_path, stack_name,
                    docker_image, has_wrapper, docker_runner_func, timeout, verbose
                ))
        
        except Exception as e:
            behavior_result["status"] = "ERROR"
            behavior_result["error"] = str(e)
            behavior_result["recommendations"].append(f"Behavior validation error: {e}")
            
            if verbose:
                print(f"   ERROR: {e}")
        
        finally:
            behavior_duration = time.time() - behavior_start
            behavior_result["end_time"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            behavior_result["total_duration_seconds"] = round(behavior_duration, 2)
        
        return behavior_result
    
    def _execute_existing_tests(
        self,
        project_path: pathlib.Path,
        artifacts_path: pathlib.Path, 
        test_discovery: Dict[str, Any],
        docker_image: str,
        has_wrapper: bool,
        docker_runner_func: Callable,
        timeout: int,
        verbose: bool
    ) -> Dict[str, Any]:
        """Execute existing tests found during discovery."""
        if verbose:
            print("Phase 2A: Existing Test Execution")
        
        test_commands = test_discovery["test_commands"]
        test_cmd = test_commands[0] if has_wrapper else test_commands[1] if len(test_commands) > 1 else test_commands[0]
        
        test_rc, test_duration = docker_runner_func(
            docker_image, test_cmd, project_path, artifacts_path, timeout
        )
        
        test_results = self.result_parser.parse_test_results(project_path, test_discovery.get("stack_name", "maven"), test_rc)
        
        execution_result = {
            "test_execution": {
                "command_executed": test_cmd,
                "return_code": test_rc,
                "duration_seconds": round(test_duration, 2),
                "test_results": test_results
            }
        }
        
        # Determine status and recommendations
        if test_rc == 0 and test_results["failed_tests"] == 0:
            execution_result["status"] = "PASS"
            execution_result["recommendations"] = ["All tests passed - behavior validated"]
            
            if verbose:
                passed = test_results["passed_tests"]
                total = test_results["total_tests"]
                print(f"   PASS: {passed}/{total} tests passed")
                
        elif test_results["failed_tests"] > 0:
            execution_result["status"] = "FAIL" 
            execution_result["recommendations"] = ["Some tests failed - behavior regression detected"]
            
            if verbose:
                failed = test_results["failed_tests"]
                print(f"   FAIL: {failed} tests failed")
                
        else:
            execution_result["status"] = "ERROR"
            if test_results["test_reports_found"]:
                execution_result["recommendations"] = ["Test infrastructure failed - tests didn't execute properly"]
            else:
                execution_result["recommendations"] = ["Test compilation/setup failed - no test reports generated"]
            
            if verbose:
                print(f"   ERROR: Test execution failed (RC: {test_rc})")
                if not test_results["test_reports_found"]:
                    print(f"   No test reports found - likely compilation or setup failure")
        
        return execution_result
    
    def _execute_smoke_tests(
        self,
        project_path: pathlib.Path,
        artifacts_path: pathlib.Path,
        stack_name: str,
        docker_image: str,
        has_wrapper: bool,
        docker_runner_func: Callable,
        timeout: int,
        verbose: bool
    ) -> Dict[str, Any]:
        """generate and execute smoke tests when no existing tests are found"""
        if verbose:
            print("Phase 2B: Smoke Test Generation & Execution")
        
        try:
            # generate smoke tests
            smoke_generation = self.smoke_generator.generate_smoke_tests(project_path, stack_name)
            
            if not smoke_generation["smoke_tests_generated"]:
                return {
                    "status": "SKIP",
                    "recommendations": ["No smoke tests could be generated"],
                    "test_execution": {
                        "command_executed": None,
                        "return_code": 0,
                        "duration_seconds": 0,
                        "test_results": {
                            "total_tests": 0,
                            "passed_tests": 0,
                            "failed_tests": 0,
                            "skipped_tests": 0,
                            "test_success_rate": 0.0,
                            "test_reports_found": False
                        }
                    },
                    "smoke_test_generation": smoke_generation
                }
            
            # execute smoke tests
            test_commands = self.test_discovery._get_test_commands_for_stack(stack_name)
            test_cmd = test_commands[0] if has_wrapper else test_commands[1] if len(test_commands) > 1 else test_commands[0]
            
            test_rc, test_duration = docker_runner_func(
                docker_image, test_cmd, project_path, artifacts_path, timeout
            )
            
            # parse results
            test_results = self.result_parser.parse_test_results(project_path, stack_name, test_rc)
            
            # clean up generated tests
            self.smoke_generator.cleanup_generated_tests(project_path)
            
            execution_result = {
                "test_execution": {
                    "command_executed": test_cmd,
                    "return_code": test_rc,
                    "duration_seconds": round(test_duration, 2),
                    "test_results": test_results
                },
                "smoke_test_generation": smoke_generation,
                "cleanup_performed": True
            }
            
            # determine status and recommendations
            if test_rc == 0 and test_results["failed_tests"] == 0:
                execution_result["status"] = "PASS"
                execution_result["recommendations"] = ["Smoke tests passed - basic behavior validated"]
                
                if verbose:
                    test_types = ", ".join(smoke_generation.get("test_types", []))
                    print(f"   PASS: Smoke tests executed - {test_types}")
                    
            elif test_results["failed_tests"] > 0:
                execution_result["status"] = "FAIL"  
                execution_result["recommendations"] = ["Smoke tests failed - potential issues detected"]
                
                if verbose:
                    failed = test_results["failed_tests"]
                    print(f"   FAIL: {failed} smoke tests failed")
                    
            else:
                execution_result["status"] = "ERROR"
                execution_result["recommendations"] = ["Smoke test execution failed"]
                
                if verbose:
                    print(f"   ERROR: Smoke test execution failed (RC: {test_rc})")
            
            return execution_result
            
        except Exception as e:
            # try cleaning up even on error
            try:
                self.smoke_generator.cleanup_generated_tests(project_path)
            except:
                pass
            
            return {
                "status": "ERROR",
                "error": str(e),
                "recommendations": [f"Smoke test execution error: {e}"],
                "test_execution": {
                    "command_executed": None,
                    "return_code": -1,
                    "duration_seconds": 0,
                    "test_results": {
                        "total_tests": 0,
                        "passed_tests": 0,
                        "failed_tests": 0,
                        "skipped_tests": 0,
                        "test_success_rate": 0.0,
                        "test_reports_found": False
                    }
                }
            }
    
    def format_behavior_results_for_display(self, behavior_result: Dict[str, Any], verbose: bool = False) -> None:
        """for console display"""
        if not behavior_result:
            if verbose:
                print("Behavior: SKIP (build failed)")
            return
        
        behavior_status = behavior_result['status']
        if verbose:        
            if behavior_status == "PASS":
                test_execution = behavior_result.get('test_execution', {})
                test_results = test_execution.get('test_results', {})
                passed = test_results.get('passed_tests', 0)
                total = test_results.get('total_tests', 0)
                print(f"Behavior: PASS ({passed}/{total} tests)")
                
            elif behavior_status == "FAIL":
                test_execution = behavior_result.get('test_execution', {})
                test_results = test_execution.get('test_results', {})
                failed = test_results.get('failed_tests', 0)
                print(f"Behavior: FAIL ({failed} tests failed)")
                
            elif behavior_status == "SKIP":
                print("Behavior: SKIP (no tests)")
                
            elif behavior_status == "ERROR":
                error_msg = behavior_result.get('error', 'Unknown error')
                print(f"Behavior: ERROR ({error_msg})")


# convenience functions for backward compatibility
def execute_behavior_validation(
    project_path: pathlib.Path, 
    artifacts_path: pathlib.Path,
    stack_name: str, 
    docker_image: str, 
    has_wrapper: bool,
    docker_runner_func: Callable,
    timeout: int = 1200, 
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Execute Behavior Check: Test discovery and execution in Docker container
    
    This function maintains backward compatibility with the original interface.
    """
    executor = TestExecutor()
    return executor.execute_behavior_validation(
        project_path, artifacts_path, stack_name, docker_image, 
        has_wrapper, docker_runner_func, timeout, verbose
    )


def format_behavior_results_for_display(behavior_result: Dict[str, Any], verbose: bool = False) -> None:
    """format behavior results for display - backward compatibility function."""
    executor = TestExecutor()
    executor.format_behavior_results_for_display(behavior_result, verbose)