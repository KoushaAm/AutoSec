# AutoSec: Automated Multi-Agent Code Remediation & Security Pipeline
Autosec is a multi-agent pipeline designed to detect, confirm, fix,
and validate security vulnerabilities for Java projects. AutoSec is
divided into 4 stages: *Finder*, *Exploiter*, *Patcher*, and *Verifier*, each
implemented through an LLM agent. The several stages aim to
combine and automate the several stages of vulnerability detection
and patching to one end-to-end pipeline.

Given a target project, the Finder agent first scans the code to
identify potential vulnerabilities and extracts the relevant code paths
and context. These candidate vulnerabilities are then passed to the
Exploiter agent, which attempts to validate them by generating
proof of vulnerability test cases and filtering out false positives.
Once a vulnerability is confirmed, the Patcher agent uses the infor-
mation produced by the Finder and Exploiter to generate a targeted
patch for the affected code. Finally, the Verifier agent evaluates the
patched program by rebuilding the project and running validation
tests to ensure that the vulnerability has been addressed without
introducing new issues.

To evaluate the AutosSec pipeline as a whole, these key metrics
were used per project: how many vulnerabilities identified and
patched were actual vulnerabilities (precision), how many of the
total vulnerabilities were identified and patched (recall), and the f1
score (balance of precision and recall).
By separating the process into specialized agents, AutoSec enables
a clear and structured end-to-end workflow where each stage can
be evaluated independently while contributing to an automated
security remediation pipeline.

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



### 5. Exploiter Setup
#### 5.1 API_KEY - temporarily a different api key is used for the Exploiter
Export your OpenAI API key as OPENAI_KEY_FAULTLINE on your OS
```
export OPENAI_KEY_FAULTLINE="your_api_key_here"
```
#### 5.2 SetUp CWE-Bench-Java
In the directory [cwe-bench-java](Agents/Exploiter/data/cwe-bench-java/) create a new folder called java-env. The folder can be empty 
since we are using Docker to build these projects.

#### 5.3 Input setup (only for Independent runs)
In order to run Exploiter Independently you need to provide this the file result.json in the location Agents/Exploiter/vuln_agent/modules/data/traces/result.json

### 6. Getting the Source/Zip file of the projects
To get other IRIS/Faultine projects into the sources & zipped directory:

0. Run the `prepare_project.sh` script to skip steps 1 through 4
```bash
chmod +x Pipeline/scripts/prepare_project.sh # first time: make it executable
./Pipeline/scripts/prepare_project.sh <project_name>
```
1. Navigate to the Agents/Finder directory: 
```bash
cd /workspaces/autosec/Agents/Finder
```
2. Run the the `fetch_one.py` script to download the project at the commit that contains the specific CVE vulnerability
```bash
python scripts/fetch_one.py <name_of_project>
# example: 
python scripts/fetch_one.py yamcs__yamcs_CVE-2023-45278_5.8.6
```
3. The project will now exist in `/workspaces/autosec/Agents/Finder/data/project-sources`. Navigate to that directory and move it to `Projects/Sources`
```bash
cd /workspaces/autosec/Agents/Finder/data/project-sources
mv ./<name_of_project> /workspaces/autosec/Projects/Sources

# example:
cd /workspaces/autosec/Agents/Finder/data/project-sources
mv ./yamcs__yamcs_CVE-2023-45278_5.8.6 /workspaces/autosec/Projects/Sources
```
4. Zip the project and move the Zipped file to `Projects/Zipped`
```bash
cd /workspaces/autosec/Projects/Sources/<project_name>
zip -r <name_of_project>.zip ./
mv ./<name_of_project>.zip /workspaces/autosec/Projects/Zipped

# example:
cd /workspaces/autosec/Projects/Sources/yamcs__yamcs_CVE-2023-45278_5.8.6
zip -r yamcs__yamcs_CVE-2023-45278_5.8.6.zip ./
mv ./yamcs__yamcs_CVE-2023-45278_5.8.6.zip /workspaces/autosec/Projects/Zipped
```


### 7. Run the Pipeline
```bash
python3 main.py

# Optional: Customize the Patcher agent code extraction limit
PATCHER_SNIPPET_MAX_LINES=800 python main.py

# For all possible arguments without running main
python3 main.py <-h|--help>
```


## Injecting Project Variants CSV
To streamline the process of loading our dataset we utilize the `generate_project_variants.py` script located in the `Pipeline/scripts` directory. Note that this script **overwrites** the existing `project_variants.py`!
1. Ensure the `AutoSec_120_Project_Variants.csv` file exists within the `Projects/` directory
2. Run the following command from the project root:
```bash
python Pipeline/scripts/generate_project_variants.py Projects/AutoSec_120_Project_Variants.csv

# You can also load other projects assuming the CSV follows the EXACT format of `AutoSec_120_Project_Variants.csv`
python Pipeline/scripts/generate_project_variants.py <formatted_csv>.csv
```
3. Check if `Pipeline/project_variants.py` has been populated with the given 120 projects listed in the Project Variants CSV
    - By default the results are saved to `Pipeline/project_variants.py`, however if desired this can be changed using the following
```bash
python Pipeline/scripts/generate_project_variants.py AutoSec_120_Project_Variants.csv --output path/to/project_variants.py
```

## Convert Finder SARIF output to JSON
1. Run analysis on the desired project, the `Finder` agent will have generated a `.sarif` file of results
2. After finder analysis run the following command from the project root:
```bash
python Pipeline/scripts/convert_to_finder_output.py <project_name> <cwe_id> <json_name>.json

# example: 
# python Pipeline/scripts/convert_to_finder_output.py perwendel__spark_CVE-2018-9159_2.7.1 cwe-022 finder_output_perwendel.json
```
3. This will create a `json` file in `Projects/Finder_Output`

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
