# Verifier/config.py
from typing import Dict
from pathlib import Path
from constants import Model

# Select OpenRouter model for patch application
CURRENT_MODEL = Model.LLAMA3 

# ===== Expose for use in other modules =====
MODEL_NAME = CURRENT_MODEL.name
MODEL_VALUE = CURRENT_MODEL.value

TOOL_VERSION = "verifier-patch-applicator-1.0.0"

# Model context limits: approximate context windows per model name
# If MODEL_NAME isn't found here, we fall back to DEFAULT_CONTEXT_LIMIT
DEFAULT_CONTEXT_LIMIT = 8192  # conservative default

MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    Model.LLAMA3.name: 8192,
    Model.QWEN3.name: 16384, 
    Model.DEEPSEEK.name: 8192,
    Model.KAT_CODER.name: 8192,
    MODEL_NAME: DEFAULT_CONTEXT_LIMIT,  # keep at least this one valid
}

# Patch application settings
PATCH_SETTINGS = {
    "temperature": 0.0,  # Use deterministic output for code
    "max_tokens": 4000,   # Sufficient for most source files
    "timeout": 30,        # API timeout in seconds
    "retry_attempts": 3,  # Number of retries on failure
}

# File paths - Updated to use correct Experiments structure
DEFAULT_PATCH_INPUT_DIR = Path("../Patcher/output")  # Patcher output directory
DEFAULT_OUTPUT_DIR = Path("output")                  # Verifier output directory
DEFAULT_ARTIFACTS_DIR = Path("artifacts")            # Build artifacts (existing)

# Latest Patcher output directory (temporary - in pipeline we'll fetch from langgraph state?)
LATEST_PATCHER_OUTPUT = Path("../Patcher/output/patcher_20251127T221131Z")

# Supported file extensions for patch application
SUPPORTED_EXTENSIONS = {".java", ".py", ".js", ".ts", ".cpp", ".c", ".h", ".hpp"}

# Dry run mode (default: True for safety)
DEFAULT_DRY_RUN = True