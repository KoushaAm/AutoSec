# Patcher/config.py
from typing import Dict
from pathlib import Path
# local imports
from .constants import Model

# Select OpenRouter model
CURRENT_MODEL = Model.LLAMA3

# Get the directory where patcher.py is located
SCRIPT_DIR = Path(__file__).parent

# ===== Expose for use in other modules =====
MODEL_NAME = CURRENT_MODEL.name
MODEL_VALUE = CURRENT_MODEL.value

TOOL_VERSION = "patcher-2.0.0"

# Set OUTPUT_PATH relative to patcher.py's directory
OUTPUT_PATH = SCRIPT_DIR / "output" # Agents/Patcher/output

# Model context limits: approximate context windows per model name,
# If MODEL_NAME isn't found here, we fall back to DEFAULT_CONTEXT_LIMIT.
DEFAULT_CONTEXT_LIMIT = 8192  # conservative default

MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Examples, update as required
    Model.LLAMA3.name: 8192,
    Model.QWEN3.name: 16384,
    Model.DEEPSEEK.name: 8192,
    Model.KAT_CODER.name: 8192,
    MODEL_NAME: DEFAULT_CONTEXT_LIMIT,  # keep at least this one valid
}