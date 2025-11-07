# Fixer Experiments
- Fixer Agent related LLM testing & experiments live here

### Tools
- [Open Router](https://openrouter.ai/)

### LLM Candidates
- Meta: Llama 3.3 70B            -> https://openrouter.ai/meta-llama/llama-3.3-70b-instruct:free
- Qwen: Qwen3 235B A22B    -> https://openrouter.ai/qwen/qwen3-235b-a22b:free/api
- DeekSeek: DeepSeek V3.1        -> https://openrouter.ai/deepseek/deepseek-chat-v3.1:free
- Mistral: Mistral Small 3.2 24B -> https://openrouter.ai/mistralai/mistral-small-3.2-24b-instruct:free
- NVIDIA: Nemotron Nano 9B V2    -> https://openrouter.ai/nvidia/nemotron-nano-9b-v2:free

### Running LLMs in Python
1. Create an Isolated Environment 
    ```bash
    # only first time
    python -m venv .venv

    # Windows (git bash):
    source .venv/Scripts/activate
    # macOS / Linux:
    source .venv/bin/activate

    # only first time
    pip install --upgrade pip
    pip install openai python-dotenv
    ```
2. Store API key in `.env`: `OPENROUTER_API_KEY=your_api_key_here`
3. Run with: `python openrouter.py`

### Pretty Print JSON
- Following the same stems as [Running LLMs in Python](#running-llms-in-python)
- Run with: `python pretty_print_json.py`
- Will output all JSON files in `output` directory in readable format

### Empty Output Directory
- Run from within `Fixer` directory
- `rm -rf output/*.json`