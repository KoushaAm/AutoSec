# Verifier Agent

**Clean, production-ready patch verification system for AutoSec pipeline**

## 📁 Directory Structure

```
Agents/Verifier/
├── verifier.py              # Main entry point
├── config.py                # Configuration settings
├── README.md               # This file
│
├── core/                    # Core verification engine
│   ├── __init__.py
│   ├── engine.py           # Main verification orchestrator
│   ├── patch_applicator.py # LLM-based patch application
│   ├── docker_runner.py    # Docker container management
│   └── project_detector.py # Java project detection
│
├── handlers/               # Specialized verification handlers
│   ├── __init__.py
│   ├── patch_parser.py     # Unified diff parsing
│   ├── build_handler.py    # Docker build verification
│   ├── pov_handler.py      # POV test execution
│   ├── llm_test_handler.py # LLM test generation
│   └── result_evaluator.py # Result analysis
│
├── models/                 # Data models
│   ├── __init__.py
│   └── verification.py     # Verification result types
│
├── testing/                # Testing infrastructure
│   ├── __init__.py
│   ├── test_discovery.py   # Test detection
│   ├── pov/               # POV test support
│   │   ├── __init__.py
│   │   └── test_compiler.py
│   └── llm/               # LLM test generation
│       ├── __init__.py
│       └── test_generator.py
│
├── utils/                  # Utilities
│   ├── __init__.py
│   └── file_ops.py        # File operations
│
└── constants/             # Shared constants (symlink to root)
    └── __init__.py
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Docker (for build verification)
- OpenRouter API key (set in `.env`)

### Basic Usage

```bash
# Verify latest Patcher output
cd Agents/Verifier
python3 verifier.py --latest-patcher

# Verify specific patch file
python3 verifier.py --input /path/to/patch.json
```

## 🔧 Components

### Core Engine (`core/engine.py`)
Main verification orchestrator that coordinates all verification steps:
1. Parse patch from Patcher output
2. Apply patch using LLM
3. Build project in Docker
4. Run existing tests
5. Generate and run LLM tests
6. Execute POV tests
7. Evaluate and aggregate results

### Handlers
- **patch_parser.py**: Parses unified diffs from Patcher
- **build_handler.py**: Manages Docker builds with JDK retry strategy
- **llm_test_handler.py**: Generates security tests using LLM
- **pov_handler.py**: Compiles and runs proof-of-vulnerability tests
- **result_evaluator.py**: Analyzes verification results

### Models
Strongly-typed data models for verification results, patch info, and test outcomes.

### Testing Infrastructure
- **test_discovery.py**: Discovers existing JUnit tests
- **pov/test_compiler.py**: Compiles POV tests against patched code
- **llm/test_generator.py**: Generates security regression tests

## 🔄 Integration with Pipeline

This agent is designed to integrate with LangGraph in the AutoSec pipeline:

```python
# Future LangGraph node structure
def verifier_node(state: PipelineState) -> PipelineState:
    verifier = create_verifier()
    results = verifier.verify_fixer_output(state.patcher_output)
    state.verification_results = results
    return state
```

## 📝 Configuration

Edit `config.py` to customize:
- Model selection (LLAMA3, QWEN3, DEEPSEEK, etc.)
- Patch application settings (temperature, max_tokens, timeout)
- File paths for input/output
- Supported file extensions

## 🧪 Testing

```bash
# Run verification on a sample patch
python3 verifier.py --input ../Patcher/output/patch_sample.json

# Check Docker availability
python3 -c "from core.docker_runner import check_docker; print(check_docker())"
```

## 📊 Output Structure

```
output/
└── verifier_TIMESTAMP/
    ├── verification_results.json  # Detailed results
    ├── summary.json              # Executive summary
    └── patched_projects/         # Patched source code
        └── PROJECT_NAME/
            └── FILE-patched.java
```

## 🔑 Key Features

✅ **LLM-Based Patch Application**: Uses OpenRouter models to intelligently apply patches  
✅ **Docker Isolation**: All builds and tests run in isolated Docker containers  
✅ **Multi-JDK Retry**: Automatically retries builds with different JDK versions  
✅ **Security Test Generation**: Creates targeted security regression tests  
✅ **POV Validation**: Compiles and runs proof-of-vulnerability tests  
✅ **Comprehensive Results**: Detailed JSON output with all verification data  

## 🛠️ Development

### Adding New Handlers
1. Create handler in `handlers/`
2. Import in `handlers/__init__.py`
3. Integrate in `core/engine.py`

### Adding New Models
1. Define data class in `models/verification.py`
2. Export in `models/__init__.py`

## 📚 Documentation

See individual module docstrings for detailed API documentation:
- `core/engine.py` - Main verification flow
- `handlers/patch_parser.py` - Patch parsing logic
- `core/patch_applicator.py` - LLM patch application

## 🔗 Related Agents

- **Patcher**: Generates patches (input to Verifier)
- **Finder**: Discovers vulnerabilities (upstream)
- **Exploiter**: Tests exploitability (downstream)

## 📄 License

Part of the AutoSec vulnerability remediation pipeline.
