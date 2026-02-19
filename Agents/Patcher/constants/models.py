from enum import Enum

class Model(Enum):
    QWEN3 = "qwen/qwen3-235b-a22b:free"
    DEEPSEEK = "deepseek/deepseek-chat-v3.1:free" 
    LLAMA3 = "meta-llama/llama-3.3-70b-instruct:free"
    NEMOTRON = "nvidia/nemotron-3-nano-30b-a3b:free" 
    KAT_CODER = "kwaipilot/kat-coder-pro:free"
    GPT5_NANO_PAID = "openai/gpt-5-nano" # $0.05/M input token, $0.40/M output tokens
    GPT5_MINI_PAID = "openai/gpt-5-mini" # $0.25/M input token, $0.40/M output tokens

"""
Notes on model selection:
- QWEN3: good performance but often uses more tokens than expected, usually hitting max token limit.
- DEEPSEEK: generally efficient with tokens and reliable for code-related tasks.
- LLAMA3: powerful but may require more careful prompt engineering.
"""