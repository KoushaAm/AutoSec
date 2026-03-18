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

### 3. Add Your OpenRouter API Key and OPENai KEY
Create `.env` in root directory:
```env
# Patcher openrouter key
OPENROUTER_API_KEY="your_api_key_here"

# Finder OpenAI Key
OPENAI_API_KEY="your_api_key_here"

# Exploiter OpenAI Key
OPENAI_KEY_FAULTLINE="your_api_key_here"
```

### 4. Create the docker container for Finder
Go to the root or `/Agents/Finder` folder and run the following
```bash
# Run from root
docker build --platform linux/amd64 -t iris:latest -f Agents/Finder/Dockerfile Agents/Finder

# Run from /Agents/Finder
docker build -f Dockerfile --platform linux/amd64 -t iris:latest .

docker run --platform=linux/amd64 -it iris:latest

# in the cli of the iris docker container
run conda activate iris
```



### 5. Make sure to have an OpenAI key for the Exploiter Module
Export your OpenAI API key as OPENAI_KEY_FAULTLINE on your OS
```
export OPENAI_KEY_FAULTLINE="your_api_key_here"
```

### 6. Run the Pipeline
```bash
python3 main.py

# Customize the Patcher agent code extraction limit
PATCHER_SNIPPET_MAX_LINES=800 python main.py


# For all possible arguments without running main
python3 main.py <-h|--help>
```


## Getting the .Zip file of the projects
To get other IRIS/Faultine projects into the zipped directory:

- Navigate to the Agents/Finder directory
```
cd /workspaces/autosec/Agents/Finder
```
- Run the the fetch_one.py script to download the project at the commit that contains the specific CVE vulnerability
```
python scripts/fetch_one.py <name_of_project>
// ex: python scripts/fetch_one.py jenkinsci__workflow-cps-plugin_CVE-2022-25173_2646.v6ed3b5b01ff1
```
- The project will now exist in /workspaces/autosec/Agents/Finder/data/project-sources. Navigate to that directory, zip it up, and move it to the  /workspaces/autosec/Projects/Zipped directory
```
cd /workspaces/autosec/Agents/Finder/data/project-sources/<project_name>
// ex: cd /workspaces/autosec/Agents/Finder/data/project-sources/jenkinsci__workflow-cps-plugin_CVE-2022-25173_2646.v6ed3b5b01ff1/

zip -r <name_of_project.zip> ./
// ex: zip -r jenkinsci__workflow-cps-plugin_CVE-2022-25173_2646.v6ed3b5b01ff1.zip ./

mv ./<name_of_project> /workspaces/autosec/Projects/Zipped
// ex: mv ./jenkinsci__workflow-cps-plugin_CVE-2022-25173_2646.v6ed3b5b01ff1.zip  /workspaces/autosec/Projects/Zipped

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
