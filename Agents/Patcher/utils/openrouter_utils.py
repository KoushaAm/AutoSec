# Patcher/utils/openrouter_utils.py
from typing import Dict, List

def combine_prompt_messages(system_msg: str, developer_msg: str, user_msg: str) -> List[Dict[str, str]]:
    """
    Always merge developer policies into the system message.

    This avoids relying on the 'developer' role (which is not consistently supported across providers/models).
    """
    combined_system = system_msg + "\n\n--- Developer policies merged ---\n" + developer_msg
    return [
        {"role": "system", "content": combined_system},
        {"role": "user", "content": user_msg},
    ]
