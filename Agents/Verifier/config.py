# Verifier/config.py
from constants.models import Model

# Select OpenRouter model for patch application
CURRENT_MODEL = Model.GPT5_MINI

TOOL_VERSION = "verifier-patch-applicator-1.0.0"

# Patch application settings
PATCH_SETTINGS = {
    "temperature": 0.0,  # Use deterministic output for code
    "max_tokens": 65536,  # Must be large enough for full file output
    "timeout": 180,       # API timeout in seconds
    "retry_attempts": 3,  # Number of retries on failure
}