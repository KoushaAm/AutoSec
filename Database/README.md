# MongoDB Database

## Requirements
- Install `MongoDB for VS Code` extension
- Local IP must be added to MongoDB cluster of choice along with a user per developer

### Running MongoDB in Python
1. Create an Isolated Environment 
    ```bash
    # only first time
    python -m venv .venv

    # Windows (git bash):
    source .venv/Scripts/activate
    # macOS / Linux:
    source .venv/bin/activate

    # only first time
    pip install "pymongo[srv]" python-dotenv
    ```
2. Store database username and password in `.env` as show by `.env.example`
3. Run with `python demo.py`
