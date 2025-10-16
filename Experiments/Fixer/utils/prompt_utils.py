# prompt_utils.py
import json

"""
Encapsulates metadata fields relevant to a vulnerability fixing agent.
Attributes:
    language (str): The programming language of the vulnerable code.
    file (str): The filename containing the vulnerability.
    function (str): The function or method signature where the vulnerability exists.
    CWE (str): The Common Weakness Enumeration identifier for the vulnerability.
    vuln_title (str): A brief title describing the vulnerability.
    constraints (dict): Constraints for the fixing task (e.g., max_lines, max_hunks, no_new_deps, keep_signature).
    pov_root_cause (str): Description of the root cause of the vulnerability.
    __init__(language="", file="", function="", CWE="", vuln_title="", constraints=None, pov_root_cause=""):
Example:
    agent_fields_example = AgentFields(
        language="Java",
        file="Vulnerable.java",
        function="public static void main(String[] args) throws Exception",
        CWE="CWE-78",
        vuln_title="Fixing a command-line injection in a Java CLI program",
        constraints={
            "max_lines": 30,
            "max_hunks": 2,
            "no_new_deps": True,
            "keep_signature": True
        },
        pov_root_cause="user input is concatenated into a shell command string and passed to Runtime.exec(), allowing command injection."
    )
"""
class AgentFields:
    def __init__(
        self,
        language="",
        file="",
        function="",
        CWE="",
        vuln_title="",
        constraints=None,
        pov_root_cause=""
    ):
        self.language = language
        self.file = file
        self.function = function
        self.CWE = CWE
        self.vuln_title = vuln_title
        self.constraints = constraints or {}
        self.pov_root_cause = pov_root_cause

    def to_dict(self):
        return {
            "language": self.language,
            "file": self.file,
            "function": self.function,
            "CWE": self.CWE,
            "vuln_title": self.vuln_title,
            "constraints": self.constraints,
            "pov_root_cause": self.pov_root_cause
        }


def build_user_msg(agent_fields, vuln_snippet: str) -> str:
    """
    Build a user message from AgentFields (or dict) and a vulnerable snippet.
    - Strings are JSON-quoted (double quotes).
    - constraints rendered as a compact JSON object (booleans lowercased).
    - returns a single string ready to send to the agent.
    """
    # Accept either AgentFields instance or plain dict
    if hasattr(agent_fields, "to_dict"):
        fields = agent_fields.to_dict()
    elif isinstance(agent_fields, dict):
        fields = agent_fields
    else:
        raise TypeError("agent_fields must be AgentFields or dict")

    # Helper to JSON-quote values (strings will be quoted)
    def jq(val):
        return json.dumps(val, ensure_ascii=False)

    # Prepare constraints JSON as a single-line JSON object
    constraints = fields.get("constraints") or {}
    constraints_json = json.dumps(constraints, separators=(", ", ": "), ensure_ascii=False)

    parts = []
    parts.append("Fields provided to the agent:")
    parts.append(f"- language: {jq(fields.get('language', ''))}")
    parts.append(f"- file: {jq(fields.get('file', ''))}")
    parts.append(f"- function: {jq(fields.get('function', ''))}")
    parts.append(f"- CWE: {jq(fields.get('CWE', ''))}")
    parts.append(f"- vuln_title: {jq(fields.get('vuln_title', ''))}")
    parts.append(f"- constraints: {constraints_json}")
    parts.append(f"- pov_root_cause: {jq(fields.get('pov_root_cause', ''))}")
    
    parts.append("\nVulnerable snippet:")
    # Keep snippet language hint dynamic if you want; here using java as in your example
    parts.append(f"```{fields.get('language', '').lower() or 'text'}")
    parts.append(vuln_snippet.strip())
    parts.append("```")

    return "\n".join(parts)
