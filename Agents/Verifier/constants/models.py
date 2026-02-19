from enum import Enum

class Model(Enum):
    QWEN3 = "qwen/qwen3-235b-a22b:free"
    DEEPSEEK = "deepseek/deepseek-chat-v3.1:free"  # Recommended for code tasks
    LLAMA3 = "meta-llama/llama-3.3-70b-instruct:free"
    KAT_CODER = "kwaipilot/kat-coder-pro:free"
    GPT4O_MINI = "openai/gpt-4o-mini"  
    GPT5_NANO = "openai/gpt-5-nano"  

"""
Notes on model selection for patch application:
- GPT5_NANO: Latest GPT-5 nano model - best for production (paid)
- GPT4O_MINI: Best for production - fast, reliable, no rate limits (paid)
- DEEPSEEK: Recommended for free tier - efficient with tokens and reliable for code-related tasks.
- LLAMA3: Powerful but rate limited (8 req/min on free tier)
- QWEN3: Good performance but often uses more tokens, may hit limits.
- KAT_CODER: Specialized for coding tasks.
"""