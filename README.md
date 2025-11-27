# AutoSec

## Getting Started
- All development must be done in a **Linux environment**
- Must have **Python 3.12 installed locally**
- The following is done from the root directory

### 1. Create a Virtual Environment
```bash
python3 -m venv .venv # only first time
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Add Your OpenRouter API Key
Create `.env` in root directory:
```env
OPENROUTER_API_KEY=your_api_key_here
```

### 4. Run the Pipeline
```bash
python3 main.py
```