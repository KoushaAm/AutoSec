"""
Single script that runs the entire iris build and analyze pipeline on a given zip file.
Will add support to input github repo links as alternative input in the future (using the fetch_and_build.py script)

"""

import sys
import argparse
import zipfile
import subprocess
from pathlib import Path

# Set up paths
THIS_SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = THIS_SCRIPT_DIR.parent
sys.path.append(str(ROOT_DIR))

from src.config import DATA_DIR, PROJECT_SOURCE_CODE_DIR


# unzip project if specified to output folder
def unzip_folder(zip_path, project_name):
    target_dir = Path(PROJECT_SOURCE_CODE_DIR) / project_name
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(target_dir)


    # flatten if zip contains an extra top folder ---
    extracted_items = list(target_dir.iterdir())
    if len(extracted_items) == 1 and extracted_items[0].is_dir():
        inner = extracted_items[0]
        for item in inner.iterdir():
            item.rename(target_dir / item.name)
        inner.rmdir()

    print(f"Extracted {zip_path} into {target_dir}")

# apply patch for build to work within the enviornment
def apply_patch_if_exists(project_name):
    patch_path = Path(DATA_DIR) / "patches" / f"{project_name}.patch"
    target_dir = Path(DATA_DIR) / "project-sources" / project_name

    if not patch_path.exists():
        print(f"No patch found for {project_name}, skipping patch step.")
        return

    print(f"Applying patch {patch_path} to {target_dir}...")

    try:
        subprocess.run(
            ["git", "apply", str(patch_path)],
            cwd=target_dir,
            check=True
        )
        print(f"Successfully applied patch for {project_name}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply patch for {project_name}: {e}")
        raise

# build project (using build one.py)
def build_project(project_name):
    # Ensure build-info directory exists
    Path(f"{DATA_DIR}/build-info").mkdir(parents=True, exist_ok=True)

    build_cmd = ["python3", f"{ROOT_DIR}/scripts/build_one.py", project_name, "--try_all"]
    subprocess.run(build_cmd, check=True)

# build codeql (db using build_codeql.dbs.py)
def build_codeql(project_name):
    build_cmd = ["python3", f"{ROOT_DIR}/scripts/build_codeql_dbs.py", "--project", project_name]
    subprocess.run(build_cmd, check=True)

# run iris analysis (using iris.py)
def run_iris_analysis(project_name, query, run_id, model, overwrite):
    build_cmd = ["python3", f"{ROOT_DIR}/src/iris.py", "--query", query, "--run-id", run_id, "--llm", model, project_name]
    if (overwrite):
        print("Overwriting previous finder analysis.")
        build_cmd.append("--overwrite")

    subprocess.run(build_cmd, check=True)

# main function that parses cli args and runs whole pipeline for finder
def main():
    parser = argparse.ArgumentParser(
        description="Given zip folders, build and run IRIS analysis for vulnerability detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python3 scripts/build_and_analyze.py --project-name perwendel__spark_CVE-2018-9159_2.7.1 --zip-path project.zip --query cwe-078wLLM --model "qwen2.5-32b"
        """
    )

    parser.add_argument("--project-name", type=str)
    parser.add_argument("--zip-path", type=Path)
    parser.add_argument("--query", type=str)
    parser.add_argument("--model", type=str)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    project_name = args.project_name
    query = args.query
    model = args.model
    overwrite = args.overwrite

    # run full pipeline. only unzip if zip-path specified
    if args.zip_path:
        zip_path = Path(args.zip_path)
        print(f"Unzipping source folder at {zip_path}")
        unzip_folder(zip_path, project_name)

    apply_patch_if_exists(project_name)
    build_project(project_name)
    build_codeql(project_name)
    run_iris_analysis(project_name, query, "test", model, overwrite)

    print("\n----------------------------------\nSuccess")

if __name__ == "__main__":
    main()