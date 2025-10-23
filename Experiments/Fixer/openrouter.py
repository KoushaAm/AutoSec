from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
import json
from typing import Any, Dict

# local imports
from constants import prompts, models
from utils import generic_utils as gu, prompt_utils as pu

# ================== Constants ==================
load_dotenv()

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

AGENT_FIELDS_EXAMPLE = pu.AgentFields(
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

VULN_SNIPPET = """
    import java.util.Scanner;
// command line injection vulnerable class
public class Vulnerable {
    public static void main(String[] args) throws Exception {
        Scanner myObj = new Scanner(System.in);
        // potential source
        String userInput = myObj.nextLine();
        String cmd = "java -version " + userInput;
        System.out.println("constructed command: " + cmd);

        // potential sink
        Runtime.getRuntime().exec(cmd);
    }
}
    """

# ================== Helper ==================
def _validate_schema(obj: Dict[str, Any]) -> None:
    """Lightweight schema checks for the new fields."""
    required_keys = [
        "plan", "unified_diff", "why_safe", "risk_notes",
        "touched_files", "assumptions", "behavior_change", "confidence"
    ]
    for k in required_keys:
        if k not in obj:
            raise ValueError(f"Missing required key: {k}")
    # Optional keys: validate types if present
    if "generated_tests" in obj and not isinstance(obj["generated_tests"], list):
        raise ValueError("generated_tests must be a list")
    if "cve_matches" in obj and not isinstance(obj["cve_matches"], list):
        raise ValueError("cve_matches must be a list")
    for k in ["verifier_verdict", "verifier_rationale", "verifier_confidence"]:
        if k in obj and obj[k] in (None, ""):
            raise ValueError(f"{k} is present but empty")


def process_llm_output(llm_output: str, model_name: str):
    """Process LLM output: extract JSON, validate, save, and print summary."""
    # Extract/parse JSON
    json_text = gu.extract_json_block(llm_output)
    obj = json.loads(json_text)
    _validate_schema(obj)

    # Save full JSON
    file_to_save = gu.utc_timestamped_filename(model_name)
    gu.save_output_to_file(file_to_save, json.dumps(obj, indent=2))

    # Pretty print summary
    print("\n=== Fixer Summary ===")
    print("Plan:", " / ".join(obj.get("plan", [])))
    if obj.get("cwe_matches"):
        print("CWE Matches:")
        for cwe in obj["cwe_matches"]:
            print(f" - {cwe.get('cwe_id')} -> sim={cwe.get('similarity')}")
    if obj.get("generated_tests"):
        print("Generated tests:")
        for t in obj["generated_tests"]:
            print(f" - {t.get('id')}: {t.get('desc')} (expected: {t.get('expected')})")
    if obj.get("verifier_verdict"):
        print(f"Verifier: {obj['verifier_verdict']} ({obj.get('verifier_confidence','?')}%)")
        print(f"Reason: {obj.get('verifier_rationale','')}")

    # Show readable diff
    print("\n=== Unified Diff ===\n")
    print(gu.prettify_unified_diff(json_text))
 
# ================== Main ==================
def main():
    CURRENT_MODEL = models.Model.QWEN3
    MODEL_VALUE = CURRENT_MODEL.value

    # Build user message using static prompt snippet or dynamic builder
    isStaticUserMessage = True
    USER_MESSAGE = prompts.USER_MESSAGE if isStaticUserMessage else pu.build_user_msg(AGENT_FIELDS_EXAMPLE, VULN_SNIPPET)

    # Get messages array
    messagesArray = pu.get_messages(client, MODEL_VALUE, prompts.SYSTEM_MESSAGE, prompts.DEVELOPER_MESSAGE, USER_MESSAGE)

    print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
    try:
        completion = client.chat.completions.create(
            model=MODEL_VALUE,
            messages=messagesArray,
            temperature=0.0,
            max_tokens=4000,
        )
    except Exception as e:
        print("OpenRouter error:", e)
        print("\n\nHint: If you see a 404 about 'Free model publication', enable it in Settings -> Privacy")
        return
    
    llm_output = completion.choices[0].message.content or ""
    if llm_output == "":
        print("No output from LLM.")
        return
    # print(llm_output) # print full raw output

    process_llm_output(llm_output, CURRENT_MODEL.name)


# execute main
if __name__ == "__main__":
    main()