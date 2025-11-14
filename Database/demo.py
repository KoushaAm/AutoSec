import logging
from os import getenv
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from bson import ObjectId  # for working with _id values

# ========== GLOBAL SETUP ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("database.demo")

# load env variables
load_dotenv()
DB_HOST = getenv("MONGO_HOST", "cluster0.z8vbz5o.mongodb.net")
DB_APP_NAME = getenv("MONGO_APP_NAME", "Cluster0")
DB_USERNAME = getenv("MONGO_SANDBOX_USERNAME")
DB_PASSWORD = getenv("MONGO_SANDBOX_PASSWORD")

if not DB_USERNAME or not DB_PASSWORD:
    raise ValueError("MONGO_SANDBOX_USERNAME and MONGO_SANDBOX_PASSWORD must be set in .env file")

# Create a MongoDB client
uri = f"mongodb+srv://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}/?appName={DB_APP_NAME}"
client = MongoClient(uri, server_api=ServerApi("1"))

# Choose a database and collection
db = client["sandbox_demo"] # this DB will be created on first write
items = db["items"]         # same for this collection

# ========== CRUD OPERATIONS ==========
def reset_collection():
    """Optional: clear out the collection so the demo is repeatable."""
    items.delete_many({})


def create_docs():
    logger.info("CRUD: create")

    # insert_one
    result_one = items.insert_one({"name": "Alpha", "value": 1, "tags": ["demo", "test"]})
    print("Inserted one with _id:", result_one.inserted_id)

    # insert_many
    result_many = items.insert_many(
        [
            {"name": "Beta", "value": 2, "tags": ["demo"]},
            {"name": "Gamma", "value": 3, "tags": ["sample", "test"]},
        ]
    )
    print("Inserted many with _ids:", result_many.inserted_ids)


def read_docs():
    logger.info("CRUD: read")

    # find_one (no filter) – any document
    one_doc = items.find_one()
    print("find_one (any doc):", one_doc)

    # find_one with filter
    beta_doc = items.find_one({"name": "Beta"})
    print("find_one({'name': 'Beta'}):", beta_doc)

    # find all docs with filter
    print("\nAll docs with value >= 2:")
    cursor = items.find({"value": {"$gte": 2}})
    for doc in cursor:
        print(" -", doc)


def update_docs():
    logger.info("CRUD: update")

    # update_one: set a new field on the document named "Alpha"
    result = items.update_one(
        {"name": "Alpha"},           # filter
        {"$set": {"value": 10, "updated": True}}  # update operator
    )
    print("Matched:", result.matched_count, "Modified:", result.modified_count)

    # verify
    alpha = items.find_one({"name": "Alpha"})
    print("Updated Alpha:", alpha)


def delete_docs():
    logger.info("CRUD: delete")

    # delete_one
    result_one = items.delete_one({"name": "Beta"})
    print("Deleted Beta count:", result_one.deleted_count)

    # delete_many
    result_many = items.delete_many({"value": {"$gte": 3}})
    print("Deleted value >= 3 count:", result_many.deleted_count)

    # show remaining
    print("\nRemaining docs:")
    for doc in items.find():
        print(" -", doc)

# ========== MAIN ==========
def main():
    # Confirm connection
    try:
        client.admin.command("ping")
        print("Connected to MongoDB Atlas ✅")
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Connection failed: {e}")
        raise SystemExit(1)
    
    print("=" * 40)
    reset_collection()

    create_docs()
    print("-" * 30)

    read_docs()
    print("-" * 30)

    update_docs()
    print("-" * 30)

    delete_docs()
    print("-" * 30)

if __name__ == "__main__":
    main()
