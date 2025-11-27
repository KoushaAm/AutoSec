# Patcher/config.py
from typing import Dict
# local imports
import constants.vuln_info as vi
from constants import Model

# Select OpenRouter model
CURRENT_MODEL = Model.DEEPSEEK 

# ===== Expose for use in other modules =====
MODEL_NAME = CURRENT_MODEL.name
MODEL_VALUE = CURRENT_MODEL.value

TOOL_VERSION = "patcher-1.4.1"

# Choose one or more vulnerability definitions to test here.
# VULNERABILITIES = [vi.CWE_78, vi.CWE_22, vi.CWE_94, vi.CWE_918]
VULNERABILITIES = [vi.CWE_78_PerfectoCredentials]


# Model context limits: approximate context windows per model name,
# If MODEL_NAME isn't found here, we fall back to DEFAULT_CONTEXT_LIMIT.
DEFAULT_CONTEXT_LIMIT = 10_000  # conservative default

MODEL_CONTEXT_LIMITS: Dict[str, int] = {
    # Examples, update to your real models:
    Model.LLAMA3.name: 8192,
    Model.QWEN3.name: 16384,
    Model.DEEPSEEK.name: 8192,
    Model.GROK.name: 8192,
    Model.KAT_CODER.name: 8192,
    MODEL_NAME: DEFAULT_CONTEXT_LIMIT,  # keep at least this one valid
}