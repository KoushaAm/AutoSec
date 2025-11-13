# Fixer Experiments
- Fixer Agent related LLM testing & experiments live here

## Developer Information

### Tools
- [Open Router](https://openrouter.ai/)

### LLM Candidates
- Meta: Llama 3.3 70B            -> https://openrouter.ai/meta-llama/llama-3.3-70b-instruct:free
- Qwen: Qwen3 235B A22B    -> https://openrouter.ai/qwen/qwen3-235b-a22b:free/api
- DeepSeek: DeepSeek V3.1        -> https://openrouter.ai/deepseek/deepseek-chat-v3.1:free
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
3. Run with: 
    ```bash
    python fixer.py # run normally

    # To save the prompt that is given to the LLM in 'output/given_prompt.txt'
    python fixer.py <-sp|--save-prompt>

    # For all possible arguments without running main
    python fixer.py <-h|--help>
    ```

### Empty Output Directory
- Run from within `Fixer` directory
- `rm -rf output/*.json`

<!-- ====================================== -->
## Implementation Information
...