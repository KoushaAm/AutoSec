ARTIFACTS ?= ./artifacts
INPUT ?= ../VulnerableFixed.java

.PHONY: build clean help

# Main build target
build:
	python3 verifier_build.py --input ${INPUT} --artifacts ${ARTIFACTS} --docker

# Build with verbose output
build-verbose:
	python3 verifier_build.py --input ${INPUT} --artifacts ${ARTIFACTS} --docker --verbose

# Clean artifacts
clean:
	rm -rf ${ARTIFACTS}

# Show help
help:
	@echo "Java Build Verifier - Available targets:"
	@echo ""
	@echo "  build         - Build project at INPUT path (default: ../VulnerableFixed.java)"
	@echo "  build-verbose - Build with verbose output"
	@echo "  clean         - Remove artifacts"
	@echo "  help          - Show this help"
	@echo ""
	@echo "Variables:"
	@echo "  INPUT         - Path to Java file/project (default: ../VulnerableFixed.java)"
	@echo "  ARTIFACTS     - Output directory (default: ./artifacts)"
	@echo ""
	@echo "Examples:"
	@echo "  make build                              # Test with VulnerableFixed.java"
	@echo "  make build INPUT=/path/to/java/project  # Build any Java project"
	@echo "  make build-verbose                      # Build with detailed output"