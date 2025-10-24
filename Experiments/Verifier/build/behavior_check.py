#!/usr/bin/env python3
import datetime
import pathlib
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any


def discover_tests(project_path: pathlib.Path, stack_name: str) -> dict:
    """Discover existing unit and integration tests in the project."""
    test_discovery = {
        "has_tests": False,
        "test_framework": None,
        "test_directories": [],
        "test_files": [],
        "test_count": 0,
        "test_commands": []
    }
    test_patterns = {
        "maven": {
            "directories": ["src/test/java", "src/it/java"],
            "file_patterns": ["**/*Test.java", "**/*Tests.java", "**/Test*.java", "**/*IT.java"],
            "frameworks": ["junit", "testng", "spock"]
        },
        "gradle": {
            "directories": ["src/test/java", "src/integrationTest/java", "src/functionalTest/java"],
            "file_patterns": ["**/*Test.java", "**/*Tests.java", "**/Test*.java", "**/*Spec.groovy"],
            "frameworks": ["junit", "testng", "spock"]
        },
        "javac": {
            "directories": ["."],
            "file_patterns": ["*Test.java", "*Tests.java", "Test*.java"],
            "frameworks": ["junit"]
        }
    }
    
    patterns = test_patterns.get(stack_name, test_patterns["javac"])
    
    for test_dir in patterns["directories"]:
        test_path = project_path / test_dir
        if test_path.exists() and test_path.is_dir():
            test_discovery["test_directories"].append(str(test_path.relative_to(project_path)))
    
    for pattern in patterns["file_patterns"]:
        test_files = list(project_path.glob(pattern))
        for test_file in test_files:
            if any(skip in str(test_file) for skip in ["target/", "build/", "out/"]):
                continue
            test_discovery["test_files"].append(str(test_file.relative_to(project_path)))
    
    test_discovery["test_count"] = len(test_discovery["test_files"])
    test_discovery["has_tests"] = test_discovery["test_count"] > 0
    
    if test_discovery["has_tests"]:
        framework = detect_test_framework(project_path, test_discovery["test_files"])
        test_discovery["test_framework"] = framework
        test_discovery["test_commands"] = get_test_commands_for_stack(stack_name)
    
    return test_discovery


def detect_test_framework(project_path: pathlib.Path, test_files: List[str]) -> str:
    framework_indicators = {
        "junit5": ["org.junit.jupiter", "@Test", "@ParameterizedTest", "@ExtendWith"],
        "junit4": ["org.junit.Test", "org.junit.Before", "org.junit.After", "@Test"],
        "testng": ["org.testng", "@Test", "@BeforeMethod", "@AfterMethod"],
        "spock": ["spock.lang", "extends Specification"]
    }
    
    framework_scores = {framework: 0 for framework in framework_indicators.keys()}
    
    sample_files = test_files[:5]
    
    for test_file in sample_files:
        try:
            file_path = project_path / test_file
            if not file_path.exists():
                continue
                
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            for framework, indicators in framework_indicators.items():
                for indicator in indicators:
                    if indicator in content:
                        framework_scores[framework] += 1
                        
        except Exception:
            continue
    
    if max(framework_scores.values()) > 0:
        return max(framework_scores, key=framework_scores.get)
    else:
        return "junit5"


def get_test_commands_for_stack(stack_name: str) -> List[str]:
    commands = {
        "maven": [
            "./mvnw test -B",
            "mvn test -B"
        ],
        "gradle": [
            "./gradlew test --no-daemon",
            "gradle test --no-daemon"
        ],
        "javac": [
            "echo 'Tests not supported for javac projects without build system'"
        ]
    }
    
    return commands.get(stack_name, commands["javac"])


def parse_test_results(project_path: pathlib.Path, stack_name: str, test_rc: int) -> dict:
    """Parse test execution results from build system output files."""
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
                maven_results = parse_maven_test_reports(full_report_path)
                merge_test_results(test_results, maven_results)
            elif stack_name == "gradle":
                gradle_results = parse_gradle_test_reports(full_report_path)
                merge_test_results(test_results, gradle_results)
    
    if test_results["total_tests"] > 0:
        test_results["test_success_rate"] = test_results["passed_tests"] / test_results["total_tests"]
    
    return test_results


def parse_maven_test_reports(report_dir: pathlib.Path) -> dict:
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


def parse_gradle_test_reports(report_dir: pathlib.Path) -> dict:
    results = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0, 
        "skipped_tests": 0,
        "failed_test_details": [],
        "test_execution_time": 0.0
    }
    
    xml_files = list(report_dir.glob("TEST-*.xml"))
    
    maven_style_results = parse_maven_test_reports(report_dir)
    return maven_style_results


def merge_test_results(target: dict, source: dict):
    target["total_tests"] += source["total_tests"]
    target["passed_tests"] += source["passed_tests"] 
    target["failed_tests"] += source["failed_tests"]
    target["skipped_tests"] += source["skipped_tests"]
    target["test_execution_time"] += source["test_execution_time"]
    target["failed_test_details"].extend(source["failed_test_details"])


def execute_behavior_validation(project_path: pathlib.Path, artifacts_path: pathlib.Path,
                               stack_name: str, docker_image: str, has_wrapper: bool,
                               docker_runner_func, timeout: int = 1200, verbose: bool = False) -> dict:
    """Execute Behavior Check: Test discovery and execution in Docker container."""
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
        test_discovery = discover_tests(project_path, stack_name)
        behavior_result["test_discovery"] = test_discovery
        
        if verbose:
            if test_discovery["has_tests"]:
                print(f"Tests: Found {test_discovery['test_count']} {test_discovery['test_framework']} test files")
            else:
                print("Tests: No tests discovered")
        if test_discovery["has_tests"]:
            if verbose:
                print("Phase 2: Test Execution")
            
            test_commands = test_discovery["test_commands"]
            test_cmd = test_commands[0] if has_wrapper else test_commands[1] if len(test_commands) > 1 else test_commands[0]
            
            test_rc, test_duration = docker_runner_func(
                docker_image, test_cmd, project_path, artifacts_path, timeout
            )
            
            test_results = parse_test_results(project_path, stack_name, test_rc)
            
            behavior_result["test_execution"] = {
                "command_executed": test_cmd,
                "return_code": test_rc,
                "duration_seconds": round(test_duration, 2),
                "test_results": test_results
            }
            
            if test_rc == 0 and test_results["failed_tests"] == 0:
                behavior_result["status"] = "PASS"
                behavior_result["recommendations"].append("All tests passed - behavior validated")
                    
            elif test_results["failed_tests"] > 0:
                behavior_result["status"] = "FAIL" 
                behavior_result["recommendations"].append("Some tests failed - behavior regression detected")
                        
            else:
                behavior_result["status"] = "ERROR"
                if test_results["test_reports_found"]:
                    behavior_result["recommendations"].append("Test infrastructure failed - tests didn't execute properly")
                else:
                    behavior_result["recommendations"].append("Test compilation/setup failed - no test reports generated")
                
                if verbose:
                    print(f"   ERROR: Test execution failed (RC: {test_rc})")
                    if not test_results["test_reports_found"]:
                        print(f"   No test reports found - likely compilation or setup failure")
        else:
            # No tests found - this would trigger Option B (smoke tests) in future
            behavior_result["status"] = "SKIP"
            behavior_result["recommendations"].append("No tests found - smoke tests needed (Option B)")
            behavior_result["test_execution"] = {
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
            }
            
            if verbose:
                print("   SKIP: No tests to execute - would need smoke test implementation")
    
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


def format_behavior_results_for_display(behavior_result: dict, verbose: bool = False) -> None:
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


# Future extension points for additional behavior validation options:

def generate_smoke_tests(project_path: pathlib.Path, stack_name: str) -> dict:
    """Option B: Generate basic smoke tests when no existing tests are found."""
    pass


def analyze_test_coverage(project_path: pathlib.Path, behavior_result: dict) -> dict:
    """Analyze code coverage from test execution results."""
    pass


def validate_test_quality(project_path: pathlib.Path, test_files: List[str]) -> dict:
    """Validate the quality of existing tests (assertions, mocking, etc)."""
    pass


if __name__ == "__main__":
    print("Behavior Check Module - Import this module to use behavior validation functionality")
    print("Key functions:")
    print("- discover_tests(): Find existing unit/integration tests")
    print("- execute_behavior_validation(): Complete behavior check pipeline")
    print("- parse_test_results(): Analyze test execution results")