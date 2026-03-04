#!/usr/bin/env python3
import pathlib
from typing import List, Dict, Any


class TestDiscovery:
    """Discovers and analyzes existing tests in Java projects"""
    
    TEST_PATTERNS = {
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
    
    def __init__(self):
        self._discovery_cache = {}
    
    def discover_tests(self, project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
        """Returns dictionary with test discovery results"""
        cache_key = f"{project_path.absolute()}:{stack_name}"
        if cache_key in self._discovery_cache:
            return self._discovery_cache[cache_key]
        
        test_discovery = {
            "has_tests": False,
            "test_framework": None,
            "test_directories": [],
            "test_files": [],
            "test_count": 0,
            "test_commands": [],
            "framework_confidence": 0.0
        }
        
        patterns = self.TEST_PATTERNS.get(stack_name, self.TEST_PATTERNS["javac"])
        
        # Discover test directories
        for test_dir in patterns["directories"]:
            test_path = project_path / test_dir
            if test_path.exists() and test_path.is_dir():
                test_discovery["test_directories"].append(str(test_path.relative_to(project_path)))
        
        # Discover test files
        for pattern in patterns["file_patterns"]:
            test_files = list(project_path.glob(pattern))
            for test_file in test_files:
                # Skip build output directories
                if any(skip in str(test_file) for skip in ["target/", "build/", "out/"]):
                    continue
                test_discovery["test_files"].append(str(test_file.relative_to(project_path)))
        
        test_discovery["test_count"] = len(test_discovery["test_files"])
        test_discovery["has_tests"] = test_discovery["test_count"] > 0
        
        if test_discovery["has_tests"]:
            framework, confidence = self._detect_test_framework(project_path, test_discovery["test_files"])
            test_discovery["test_framework"] = framework
            test_discovery["framework_confidence"] = confidence
            test_discovery["test_commands"] = self._get_test_commands_for_stack(stack_name)
        
        # Cache result
        self._discovery_cache[cache_key] = test_discovery
        
        return test_discovery
    
    def _detect_test_framework(self, project_path: pathlib.Path, test_files: List[str]) -> tuple[str, float]:
        """Returns tuple of (framework_name, confidence_score)"""
        framework_indicators = {
            "junit5": ["org.junit.jupiter", "@Test", "@ParameterizedTest", "@ExtendWith"],
            "junit4": ["org.junit.Test", "org.junit.Before", "org.junit.After", "@Test"],
            "testng": ["org.testng", "@Test", "@BeforeMethod", "@AfterMethod"],
            "spock": ["spock.lang", "extends Specification"]
        }
        
        framework_scores = {framework: 0 for framework in framework_indicators.keys()}
        total_indicators = 0
        
        # Sample few test files for analysis
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
                            total_indicators += 1
                            
            except Exception:
                continue
        
        if total_indicators == 0:
            return "junit5", 0.0
        
        # Find the framework with the highest score
        best_framework = max(framework_scores, key=framework_scores.get)
        confidence = framework_scores[best_framework] / total_indicators
        
        return best_framework, confidence
    
    def _get_test_commands_for_stack(self, stack_name: str) -> List[str]:
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
                # Compile tests and run with JUnit console launcher
                "javac -cp .:junit-platform-console-standalone.jar:. *Test.java && java -jar junit-platform-console-standalone.jar --class-path . --scan-class-path",
                # Fallback: just compile to verify syntax
                "javac -cp . *Test.java"
            ]
        }
        
        return commands.get(stack_name, commands["javac"])