from enum import Enum

# ALWAYS provide root relative path, this should be what final .SARIF provides too
VULN_DIR = "Experiments/vulnerable/"

class VulnerabilityInfo(Enum):
    """Base class for vulnerability information with required attributes."""
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Verify that the class has all required attributes
        required_attrs = {'FILE_PATH', 'FILE_NAME', 'CWE', 'START_LINE', 'END_LINE'}
        class_attrs = {name for name in dir(cls) if not name.startswith('_')}
        
        if not required_attrs.issubset(class_attrs):
            missing = required_attrs - class_attrs
            raise TypeError(
                f"{cls.__name__} must define all required attributes: {missing}"
            )

# ================== Vulnerability Definitions ==================
class CWE_22(VulnerabilityInfo):
    FILE_PATH = f"{VULN_DIR}CWE_22.java"
    FILE_NAME = "CWE_22.java"
    CWE = "CWE-22"
    START_LINE = 15 
    END_LINE = 27

class CWE_78(VulnerabilityInfo):
    FILE_PATH = f"{VULN_DIR}CWE_78.java"
    FILE_NAME = "CWE_78.java"
    CWE = "CWE-78"
    START_LINE = 5 
    END_LINE = 14