from enum import Enum

class Model(Enum):
    QWEN3 = "qwen/qwen3-235b-a22b:free"                   # Developer role supported
    DEEPSEEK = "deepseek/deepseek-chat-v3.1:free"     # Developer role supported
    LLAMA3 = "meta-llama/llama-3.3-70b-instruct:free" # Developer role supported
    # GPT_OSS = "openai/gpt-oss-20b:free"               # Developer role NOT supported
    # NEMOTRON_NANO = "nvidia/nemotron-nano-9b-v2:free" # Developer role NOT supported

"""
Notes on model selection:
- QWEN3: good performance but often uses more tokens than expected, usually hitting max token limit.
- DEEPSEEK: generally efficient with tokens and reliable for code-related tasks.
- LLAMA3: powerful but may require more careful prompt engineering.
"""