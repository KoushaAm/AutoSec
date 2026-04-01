"""
The main module for the AutoSec application.

This module initializes the LangGraph state graph and starts the execution
of the defined workflow. It serves as the entry point for the application.

Children modules:
- Pipeline/pipeline.py: Defines the workflow graph and nodes.
- Agents/*: Contains various agent implementations.

usage: python main.py --project PROJECT_NAME # PROJECT_NAME from Pipeline/project_variants. if no --project, default one is used

"""
import logging
import argparse
# local imports
from Pipeline import pipeline_main, project_variants

# logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== Execute AutoSec =====
def main():
    logger.info("Running AutoSec...")

    parser = argparse.ArgumentParser()
    parser.add_argument(
    "--project",
    type=str,
    default="WORKFLOW_CPS", # default project if
    choices=[e.name for e in project_variants.ProjectVariants]  # <-- uses enum names
    )
    args = parser.parse_args()

    selected_project = project_variants.ProjectVariants[args.project]
    pipeline_main(selected_project)

    logger.info("AutoSec run complete.")


if __name__ == "__main__":
    main()