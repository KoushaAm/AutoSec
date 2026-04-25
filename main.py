"""
The main module for the AutoSec application.

This module initializes the LangGraph state graph and starts the execution
of the defined workflow. It serves as the entry point for the application.

Children modules:
- Pipeline/pipeline.py: Defines the workflow graph and nodes.
- Agents/*: Contains various agent implementations.

"""
import logging
import argparse
# local imports
from Pipeline import pipeline_main

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== Execute AutoSec =====
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project",
        help="Project name to run, e.g. rhuss__jolokia_CVE-2018-1000129_1.4.0",
    )
    args = parser.parse_args()

    logger.info("Running AutoSec...")
    pipeline_main(project_name=args.project)
    logger.info("AutoSec run complete.")


if __name__ == "__main__":
    main()