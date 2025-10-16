import json
from datetime import datetime, timezone
from pathlib import Path
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

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

# # ================== Helper ==================
def process_llm_output(llm_output, model_name):
    # remove ``` if present
    stripped_llm_output = gu.strip_code_fence(llm_output)

    # Save full output
    file_to_save = gu.utc_timestamped_filename(model_name)
    gu.save_output_to_file(file_to_save, stripped_llm_output)

    # Show readable diff
    print("\n=== Unified Diff ===\n")
    print(gu.prettify_unified_diff(stripped_llm_output))

# ================== Main ==================
def main():
    CURRENT_MODEL = models.Model.GPT_OSS

    messagesArray = [
        {"role": "system", "content": prompts.SYSTEM_MESSAGE},
        {"role": "developer", "content": prompts.DEVELOPER_MESSAGE},
        # {"role": "user", "content": prompts.USER_MESSAGE},
        {"role": "user", "content": pu.build_user_msg(AGENT_FIELDS_EXAMPLE, VULN_SNIPPET)},
    ]

    try:
        completion = client.chat.completions.create(
            model=CURRENT_MODEL.value,
            messages=messagesArray,
            temperature=0.0,
            max_tokens=3000,
        )
    except Exception as e:
        print("OpenRouter error:", e)
        print("\nHint: If you see a 404 about 'Free model publication', enable it in Settings -> Privacy")
        return
    llm_output = completion.choices[0].message.content
    # print(llm_output) # print full raw output

    process_llm_output(llm_output, CURRENT_MODEL.name)


# execute main
if __name__ == "__main__":
    main()