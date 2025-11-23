# Patcher Experiments

This module contains the experimental and evolving implementation of the **AutoSec Patcher Agent**.  
The Patcher uses large language models (LLMs) to generate **minimal, correct, and verifiable security patches** for vulnerable code using strict schemas, code context extraction, and data-flow information.


## Getting Started
- All development must be done in a **Linux environment**
- Must have **Python 3.11 installed locally**

### 1. Create a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
# install tree-sitter directly fallback if needed
pip install "git+https://github.com/tree-sitter/py-tree-sitter-languages.git"
```

### 3. Add Your OpenRouter API Key
Create .env in this directory:
```env
OPENROUTER_API_KEY=your_api_key_here
```

### 4. Run the Patcher
```bash
python3 patcher.py

# To save the prompt that is given to the LLM in 'output/given_prompt.txt'
python3 patcher.py <-sp|--save-prompt>

# For all possible arguments without running main
python3 patcher.py <-h|--help>
```

### 5. Cleaning Output
- Artifacts are written to: `Experiments/Patcher/output/`
- Remove generated JSON files: `rm -rf output/*.json`


## Project Structure
```
Experiments/
├── Patcher/
│   ├── core/
│   │   ├── types.py                # Global Strongly-typed structures
│   │   ├── code_extractor.py       # Code Extractor
│   │   └── method_locator/         # Tree-sitter method boundary detection/
│   │       ├── java.py
│   │       └── ...
│   ├── constants/
│   │   ├── models.py               # LLM model enums
│   │   ├── prompts.py              # System + developer prompts
│   │   └── vuln_info.py            # Vulnerability definitions (CWE)
│   ├── utils/
│   │   ├── generic_utils.py        # JSON / file helpers
│   │   ├── openrouter_utils.py     # LLM API helpers
│   │   └── prompt_utils.py         # Prompt assembly
│   ├── info/                       # Detailed design & docs
│   ├── output/                     # Generated patches & artifacts
│   ├── patcher.py                  # Main CLI entrypoint
│   ├── README.md 
│   └── requirements.txt 
└── vulnerable/                     # Java examples used for testing/
    ├── CWE_22.java
    └── ...
```