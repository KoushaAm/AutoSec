import json
from datetime import datetime, timezone
from pathlib import Path
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

# local imports
from constants import prompts, models

# ================== Constants ==================
load_dotenv()

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

messagesArray = [
    {"role": "system", "content": prompts.SYSTEM_MESSAGE},
    {"role": "developer", "content": prompts.DEVELOPER_MESSAGE},
    {"role": "user", "content": prompts.USER_MESSAGE},
]

# ================== Functions ==================
def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"

def strip_code_fence(text: str) -> str:
    """
    Remove a leading/trailing triple-backtick fence, optionally with a language tag.
    If no fence present, returns the text unchanged.
    """
    text = text.strip()
    if text.startswith("```"):
        # remove leading fence line
        # find the first newline after the opening fence
        idx = text.find("\n")
        if idx != -1:
            # drop the opening fence line
            text = text[idx+1:]
        # remove trailing fence (```), if present
        if text.endswith("```"):
            text = text[: -3].rstrip()
    return text

def save_output_to_file(filename: str, content: str):
    Path("output").mkdir(parents=True, exist_ok=True) # ensure output dir exists

    p = Path("output") / filename
    # Try to pretty-validate JSON; if it fails, save raw for debugging
    try: 
        obj = json.loads(content)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        p.write_text(content, encoding="utf-8")
    print("Wrote", p)

def prettify_unified_diff(model_output: str) -> str:
    try:
        response = json.loads(model_output)
        diff = response.get("unified_diff") or ""
        return diff.replace("\\n", "\n")
    except json.JSONDecodeError:
        return "(No JSON / unified_diff not found)"

# ================== Main ==================
def main():
    CURRENT_MODEL = models.Model.LLAMA3

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

    # remove ``` if present
    stripped_llm_output = strip_code_fence(llm_output)

    # Save full output
    file_to_save = utc_timestamped_filename(CURRENT_MODEL.name)
    save_output_to_file(file_to_save, stripped_llm_output)

    # Show readable diff
    print("\n=== Unified Diff ===\n")
    print(prettify_unified_diff(stripped_llm_output))


# execute main
if __name__ == "__main__":
    main()
