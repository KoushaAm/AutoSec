# AutoSec

## Getting Started
- All development should be done inside the provided dev container
- The following is done from the root directory

### 0. Launch Dev Container
- Open the project in VS Code, then run "Dev Containers: Reopen in Container" from the Command Palette (Ctrl+Shift+P).

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

### 4. Create the docker container for Finder
Go to the root or `/Agents/Finder` folder and run the following
```bash
# Run from root
docker build --platform linux/amd64 -t iris:latest -f Agents/Finder/Dockerfile Agents/Finder

# Run from /Agents/Finder
docker build -f Dockerfile --platform linux/amd64 -t iris:latest .

docker run --platform=linux/amd64 -it iris:latest
```


### 5. Run the Pipeline
```bash
python3 main.py

# Save the Patcher Agent prompt
python3 main.py <-sp|--save-prompt>

# For all possible arguments without running main
python3 main.py <-h|--help>
```


## Project Structure
- Only files relevant to the primary AutoSec Pipeline have been listed
```
AutoSec/
├── Agents/
│   ├── Exploiter
│   ├── Finder
│   ├── Patcher
│   └── Verifier
├── Pipeline/
│   ├── __init__.py
│   └── pipeline.py
├── Projects/
│   └── <list of test projects>
├── .env
├── main.py
├── README.md
└── requirements.txt
```