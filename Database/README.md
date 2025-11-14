# MongoDB Database

## Requirements
- Install `MongoDB for VS Code` extension
- **Security Note:** Ensure that you enable IP access list restrictions in your MongoDB Atlas cluster to prevent unauthorized access. Only trusted IP addresses (such asa a local development machine) should be allowed. See [MongoDB Atlas IP Access List documentation](https://www.mongodb.com/docs/atlas/security/ip-access-list/) for more information

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
2. Store database username and password in `.env` as shown by `.env.example`
3. Run with `python demo.py`
4. Exit virtual environment with `deactivate`
