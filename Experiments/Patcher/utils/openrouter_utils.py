from typing import List

# ============= Helper functions for OpenRouter interaction =============
def _supports_developer_role(client, model):
    """Check if the model supports 'developer' role by sending a test message."""
    test_msgs = [
        {"role": "system", "content": "You are an obedient assistant."},
        {"role": "developer", "content": "If you see this, answer DEVELOPER_OK only."},
        {"role": "user", "content": "What do you reply?"}
    ]
    try:
        req = client.chat.completions.create(model=model, messages=test_msgs, max_tokens=100)
        res = req.choices[0].message.content
        return "DEVELOPER_OK" in (res or "")
    except Exception:
        return False


# ============= Externally Visible =============
# Build messages array for OpenRouter chat completion
def format_prompt_message(client, model, system_msg, developer_msg, user_msg, ignore_developer_support_check=False) -> List[dict]:
    """
    Build messages array for OpenRouter chat completion.
    If the model does not support 'developer' role, merge developer policies into system message.
    """
    if not ignore_developer_support_check and not _supports_developer_role(client, model):
        print(f"[warning] Model {model} may not support 'developer' role; merging into system message \n")
        return combine_prompt_messages(system_msg, developer_msg, user_msg)
    return [
        {"role": "system", "content": system_msg},
        {"role": "developer", "content": developer_msg},
        {"role": "user", "content": user_msg},
    ]


# Always Combine system and developer messages
def combine_prompt_messages(system_msg, developer_msg, user_msg) -> List[dict]:
    combined_system = system_msg + "\n\n--- Developer policies merged ---\n" + developer_msg
    return [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": user_msg},
    ]