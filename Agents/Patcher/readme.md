# Agents/Patcher

## File Structure
```
Agents/
└── Patcher/
    ├── constants/
    │   ├── __init__.py             
    │   ├── models.py               # LLM model enums
    │   ├── prompts.py              # System + developer prompts
    │   └── vuln_info.py            # Vulnerability definitions (CWE)
    ├── core/
    │   ├── method_locator/         # Tree-sitter method boundary detection/
    │   │   ├── __init__.py
    │   │   ├── java_method_locator.py
    │   │   └── <language_method_locator.py expansions>
    │   ├── __init__.py                
    │   ├── code_extractor.py       # Code Extractor
    │   └── types.py                # Global Strongly-typed structures
    ├── output/                     # Generated patches & artifacts
    ├── utils/
    │   ├── __init__.py
    │   ├── generic_utils.py        # JSON / file helpers
    │   ├── openrouter_utils.py     # LLM API helpers
    │   ├── output_utils.py         # LLM output helpers
    │   └── prompt_utils.py         # Prompt assembly
    ├── __init__.py
    ├── config.py                
    ├── patcher.py                  # Main CLI entrypoint
    └── readme.md
```

### Run Patcher Only
- Static Module Check: `python3 -m Agents.Patcher.patcher --help`
- Prompt-only dry-run: `python3 Agents/Patcher/patcher.py -sp`

### Remove old output artifacts
- `rm -rf Agents/Patcher/output/*`