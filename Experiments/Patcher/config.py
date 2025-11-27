# Patcher/config.py
import constants.vuln_info as vi
from constants import Model

# Select OpenRouter model
CURRENT_MODEL = Model.QWEN3 

# ===== Expose for use in other modules =====
TOOL_VERSION = "patcher-1.4.0"

MODEL_NAME = CURRENT_MODEL.name
MODEL_VALUE = CURRENT_MODEL.value

# Choose one or more vulnerability definitions to test here.
# VULNERABILITIES = [vi.CWE_78, vi.CWE_22, vi.CWE_94, vi.CWE_918]
VULNERABILITIES = [vi.CWE_78_PerfectoCredentials]