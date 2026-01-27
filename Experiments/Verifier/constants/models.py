from enum import Enum

class Model(Enum):
    QWEN3 = "qwen/qwen3-235b-a22b:free"
    DEEPSEEK = "deepseek/deepseek-chat-v3.1:free"  # Recommended for code tasks
    LLAMA3 = "meta-llama/llama-3.3-70b-instruct:free"
    KAT_CODER = "kwaipilot/kat-coder-pro:free"

"""
Notes on model selection for patch application:
- DEEPSEEK: Recommended - efficient with tokens and reliable for code-related tasks.
- LLAMA3: Powerful but may require more careful prompt engineering.
- QWEN3: Good performance but often uses more tokens, may hit limits.
- KAT_CODER: Specialized for coding tasks.
"""