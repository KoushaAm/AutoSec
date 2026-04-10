import json
import sys
from pathlib import Path
import argparse

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from Agents.Finder.src.output_converter import sarif_to_finder_output


def main():
    parser = argparse.ArgumentParser(description="Convert SARIF results to FinderOutput JSON")

    parser.add_argument("project_name", help="Project folder name under Agents/Finder/output")
    parser.add_argument("cwe_id", help="CWE id like cwe-022")
    parser.add_argument("output_json", help="Output JSON filename")

    args = parser.parse_args()

    project_name = args.project_name
    cwe_id = args.cwe_id
    output_json = args.output_json

    sarif_path = (
        ROOT_DIR
        / "Agents"
        / "Finder"
        / "output"
        / args.project_name
        / "test"
        / f"{args.cwe_id}wLLM-posthoc-filter"
        / "results.sarif"
    )

    if not sarif_path.exists():
        print(f"ERROR: SARIF file not found: {sarif_path}")
        sys.exit(1)

    # Load SARIF
    with open(sarif_path, "r", encoding="utf-8") as f:
        findings = json.load(f)

    finder_output = sarif_to_finder_output(findings, cwe_id=cwe_id)

    output_dir = ROOT_DIR / "Projects" / "Finder_Output"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / args.output_json

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(finder_output, f, indent=4)

    print(f"Saved converted output to {output_path}")


if __name__ == "__main__":
    main()