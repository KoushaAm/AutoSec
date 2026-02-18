"""
The main module for the AutoSec application.

This module initializes the LangGraph state graph and starts the execution
of the defined workflow. It serves as the entry point for the application.

Children modules:
- Pipeline/pipeline.py: Defines the workflow graph and nodes.
- Agents/*: Contains various agent implementations.

"""
import logging
# local imports
from Pipeline import pipeline_main

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== Execute AutoSec =====
def main():
    logger.info("Running AutoSec...")

    pipeline_main()

    logger.info("AutoSec run complete.")


if __name__ == "__main__":
    main()