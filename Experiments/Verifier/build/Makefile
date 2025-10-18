ARTIFACTS ?= ./artifacts
INPUT ?= .

.PHONY: build clean help test-single test-maven test-gradle list-inputs

# Main build target - defaults to current directory detection
build:
	python3 verifier_build.py --input ${INPUT} --artifacts ${ARTIFACTS} --docker

# verbose output
build-verbose:
	python3 verifier_build.py --input ${INPUT} --artifacts ${ARTIFACTS} --docker --verbose

# predefined test targets for different project types
test-single:
	@echo "Testing with single Java file..."
	python3 verifier_build.py --input ../VulnerableFixed.java --artifacts ${ARTIFACTS} --docker --verbose

test-maven:
	@echo "Testing with Spring Boot Maven project..."
	python3 verifier_build.py --input ../test_springboot_project --artifacts ${ARTIFACTS} --docker --verbose

test-gradle:
	@echo "Testing with Gradle project..."
	@echo "Note: Create a Gradle test project or specify INPUT=path/to/gradle/project"
	python3 verifier_build.py --input ${INPUT} --artifacts ${ARTIFACTS} --docker --verbose

# available test inputs
list-inputs:
	@echo "Available test inputs in the workspace:"
	@echo ""
	@echo "Single Java Files:"
	@find .. -maxdepth 1 -name "*.java" -exec basename {} \; 2>/dev/null || echo "  (none found)"
	@echo ""
	@echo "Maven Projects:"
	@find .. -maxdepth 2 -name "pom.xml" -exec dirname {} \; | sed 's|^\.\./||' 2>/dev/null || echo "  (none found)"
	@echo ""
	@echo "Gradle Projects:"
	@find .. -maxdepth 2 -name "build.gradle*" -exec dirname {} \; | sed 's|^\.\./||' 2>/dev/null || echo "  (none found)"
	@echo ""
	@echo "Usage Examples:"
	@echo "  make test-single                        # Test with VulnerableFixed.java"
	@echo "  make test-maven                         # Test with Spring Boot project"
	@echo "  make build INPUT=../VulnerableFixed.java # Custom single file"
	@echo "  make build INPUT=../test_springboot_project # Custom Maven project"

clean:
	rm -rf ${ARTIFACTS}

help:
	@echo "Java Build Verifier - Available targets:"
	@echo ""
	@echo "  build         - Build project at INPUT path (default: current directory)"
	@echo "  build-verbose - Build with verbose output"
	@echo "  test-single   - Test with single Java file (VulnerableFixed.java)"
	@echo "  test-maven    - Test with Maven project (Spring Boot demo)"
	@echo "  test-gradle   - Test with Gradle project"
	@echo "  list-inputs   - Show available test inputs in workspace"
	@echo "  clean         - Remove artifacts"
	@echo "  help          - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  INPUT         - Path to Java file/project (default: current directory)"
	@echo "  ARTIFACTS     - Output directory (default: ./artifacts)"
	@echo ""
	@echo "Examples:"
	@echo "  make test-single                        # Quick test with single file"
	@echo "  make test-maven                         # Test Maven build detection"
	@echo "  make build INPUT=/path/to/project       # Test custom project"
	@echo "  make list-inputs                        # See available test inputs"