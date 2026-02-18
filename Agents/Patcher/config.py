# Patcher/config.py
import os
from typing import Dict
from pathlib import Path
# local imports
from .constants import Model

# Get the directory where patcher.py is located
SCRIPT_DIR = Path(__file__).parent

# Set OUTPUT_PATH relative to patcher.py's directory
OUTPUT_PATH = SCRIPT_DIR / "output" # Agents/Patcher/output

# Select OpenRouter model
CURRENT_MODEL = Model.GPT5_NANO_PAID
MODEL_NAME = CURRENT_MODEL.name
MODEL_VALUE = CURRENT_MODEL.value

TOOL_VERSION = "patcher-2.1.0"

# max lines for extracted snippets (per file), controllable through env var
# example command: PATCHER_SNIPPET_MAX_LINES=800 python main.py
SNIPPET_MAX_LINES = int(os.getenv("PATCHER_SNIPPET_MAX_LINES", "400"))
print(f"[Patcher] Using SNIPPET_MAX_LINES={SNIPPET_MAX_LINES} for code extraction")

# Model context limits: approximate context windows per model name,
# If MODEL_NAME isn't found here, we fall back to DEFAULT_CONTEXT_LIMIT.
DEFAULT_CONTEXT_LIMIT = 8192  # conservative default

MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Examples, update as required
    Model.LLAMA3.name: 8192,
    Model.QWEN3.name: 16384,
    Model.KAT_CODER.name: 8192,
    Model.GPT5_NANO_PAID.name: 8192,
    MODEL_NAME: DEFAULT_CONTEXT_LIMIT,  # keep at least this one valid
}