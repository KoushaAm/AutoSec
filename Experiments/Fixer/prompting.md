# Fixer: Prompt Engineering
Prompting Guide & Info

<!-- ============================================= -->
## Concept 
- We will follow the 3-message pattern of 
    1. System message (fixer stance)
    2. Developer message (tool contract + workflow)
    3. User message (task instance)
- Keep patches minimal & function-scoped
- return machine-consumable JSON and unified diff

<!-- ============================================= -->
## Example Prompt: Command Line Injection in Java
- Example can be found in Found within `Experiments\Fixer\constants\prompts.py`