from .models import Model
from .prompts import SYSTEM_MESSAGE, DEVELOPER_MESSAGE
from .vuln_info import VulnerabilityInfo
from .vuln_experiment import (
    CWE_78,
    CWE_22,
    CWE_94,
    CWE_918,
    CWE_78_PerfectoCredentials,
)

VULNERABILITY_EXPERIMENTS = {
    "CWE-78": CWE_78,
    "CWE-22": CWE_22,
    "CWE-94": CWE_94,
    "CWE-918": CWE_918,
    "CWE-78-Perfecto": CWE_78_PerfectoCredentials,
}

__all__ = [
    "Model",
    "SYSTEM_MESSAGE",
    "DEVELOPER_MESSAGE",
    "VulnerabilityInfo",
    "VULNERABILITY_EXPERIMENTS",
]
