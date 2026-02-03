from enum import Enum

class Model(Enum):
    QWEN3 = "qwen/qwen3-235b-a22b:free"
    DEEPSEEK = "deepseek/deepseek-chat-v3.1:free"
    LLAMA3 = "meta-llama/llama-3.3-70b-instruct:free"
    # GROK = "x-ai/grok-4.1-fast:free" 
    KAT_CODER = "kwaipilot/kat-coder-pro:free"

"""
Notes on model selection:
- QWEN3: good performance but often uses more tokens than expected, usually hitting max token limit.
- DEEPSEEK: generally efficient with tokens and reliable for code-related tasks.
- LLAMA3: powerful but may require more careful prompt engineering.
"""