#!/usr/bin/env python3
"""
Find TP paths that were killed by LLM post-hoc filtering.
Shows concrete evidence of real vulnerabilities being filtered out.

Usage:
  python find_killed_tps.py <project_slug> <run_id> <query>

Example:
  python find_killed_tps.py apache__uima-uimaj_CVE-2022-32287_3.3.0 alex_gpt5mini_uima cwe-022wLLM
"""

import json
import pandas as pd
import os
import sys

IRIS_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = f"{IRIS_ROOT}/output"
FIX_INFO_PATH = f"{IRIS_ROOT}/data/fix_info.csv"


def load_fixed_methods(project_slug):
    fix_info = pd.read_csv(FIX_INFO_PATH)
    project_fix = fix_info[fix_info["project_slug"] == project_slug]
    fixed_methods = set()
    fixed_files = set()
    for _, row in project_fix.iterrows():
        f, c, m = row["file"], row["class"], row["method"]
        if "src/test" in str(f):
            continue
        fixed_files.add(f)
        fixed_methods.add(f"{f}:{c}:{m}")
    return fixed_files, fixed_methods, project_fix


def extract_passing_methods(path_nodes, project_classes, project_methods):
    """Given a list of path nodes from posthoc results.json, find enclosing methods."""
    methods = set()
    for node in path_nodes:
        file_url = node["file_url"]
        start_line = node["start_line"]
        # Find enclosing class
        rel_classes = project_classes[
            (project_classes["file"] == file_url) &
            (project_classes["start_line"] <= start_line) &
            (project_classes["end_line"] >= start_line)
        ].sort_values(by="start_line", ascending=False)
        if len(rel_classes) == 0:
            continue
        cls = rel_classes.iloc[0]["name"]
        # Find enclosing method
        rel_methods = project_methods[
            (project_methods["file"] == file_url) &
            (project_methods["start_line"] <= start_line) &
            (project_methods["end_line"] >= start_line)
        ].sort_values(by="start_line", ascending=False)
        if len(rel_methods) == 0:
            continue
        meth = rel_methods.iloc[0]["name"]
        methods.add(f"{file_url}:{cls}:{meth}")
    return methods


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    project_slug = sys.argv[1]
    run_id = sys.argv[2]
    query = sys.argv[3]

    run_dir = f"{OUTPUT_DIR}/{project_slug}/{run_id}"
    posthoc_json_path = f"{run_dir}/{query}-posthoc-filter/results.json"
    class_locs_path = f"{run_dir}/fetch_class_locs/results.csv"
    func_locs_path = f"{run_dir}/fetch_func_locs/results.csv"

    # Load data
    fixed_files, fixed_methods, fix_df = load_fixed_methods(project_slug)
    posthoc_results = json.load(open(posthoc_json_path))
    project_classes = pd.read_csv(class_locs_path)
    project_methods = pd.read_csv(func_locs_path)

    print("=" * 80)
    print(f"PROJECT: {project_slug}")
    print(f"RUN:     {run_id}")
    print(f"QUERY:   {query}")
    print("=" * 80)
    print(f"\nGround truth fixed methods ({len(fixed_methods)}):")
    for fm in sorted(fixed_methods):
        print(f"  - {fm}")

    # Classify each posthoc entry
    kept_tp = []
    killed_tp = []
    kept_fp = []
    killed_fp = []
    parse_errors = 0

    for entry in posthoc_results:
        rid = entry["result_id"]
        cfid = entry["code_flow_id"]
        info = entry["entry"]
        path_nodes = info["path"]
        result = info.get("result")

        if result is None or not isinstance(result, dict):
            parse_errors += 1
            continue

        is_vuln = result.get("is_vulnerable", False)
        explanation = result.get("explanation", "")
        src_fp = result.get("source_is_false_positive", False)
        sink_fp = result.get("sink_is_false_positive", False)

        # Check if this path is a TP (passes through fixed method)
        passing = extract_passing_methods(path_nodes, project_classes, project_methods)
        is_tp = len(fixed_methods.intersection(passing)) > 0
        matched = fixed_methods.intersection(passing)

        record = {
            "result_id": rid,
            "code_flow_id": cfid,
            "is_tp": is_tp,
            "llm_said_vulnerable": is_vuln,
            "src_fp": src_fp,
            "sink_fp": sink_fp,
            "explanation": explanation,
            "matched_methods": matched,
            "source": path_nodes[0]["message"] if path_nodes else "?",
            "sink": path_nodes[-1]["message"] if path_nodes else "?",
            "source_file": path_nodes[0]["file_url"] if path_nodes else "?",
            "sink_file": path_nodes[-1]["file_url"] if path_nodes else "?",
            "num_steps": len(path_nodes),
        }

        if is_tp and is_vuln:
            kept_tp.append(record)
        elif is_tp and not is_vuln:
            killed_tp.append(record)
        elif not is_tp and is_vuln:
            kept_fp.append(record)
        else:
            killed_fp.append(record)

    # Summary
    total = len(kept_tp) + len(killed_tp) + len(kept_fp) + len(killed_fp)
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total paths analyzed by LLM:  {total} (+ {parse_errors} parse errors)")
    print(f"  Kept TPs    (correct):      {len(kept_tp)}")
    print(f"  Killed TPs  (BAD - lost):   {len(killed_tp)}  ← these are the problem")
    print(f"  Killed FPs  (correct):      {len(killed_fp)}")
    print(f"  Kept FPs    (wrong):        {len(kept_fp)}")
    if len(killed_tp) + len(kept_tp) > 0:
        tp_kill_rate = len(killed_tp) / (len(killed_tp) + len(kept_tp)) * 100
        print(f"\n  TP Kill Rate: {tp_kill_rate:.1f}% of real TPs were incorrectly filtered out")

    # Show killed TPs in detail
    if killed_tp:
        print(f"\n{'=' * 80}")
        print(f"KILLED TRUE POSITIVES — {len(killed_tp)} real vuln paths removed by LLM")
        print(f"{'=' * 80}")
        for i, rec in enumerate(killed_tp):
            print(f"\n--- Killed TP #{i+1} (result={rec['result_id']}, flow={rec['code_flow_id']}) ---")
            print(f"  Source: {rec['source']}  [{rec['source_file']}]")
            print(f"  Sink:   {rec['sink']}  [{rec['sink_file']}]")
            print(f"  Steps:  {rec['num_steps']}")
            print(f"  Matched fix method(s): {rec['matched_methods']}")
            print(f"  LLM source_is_FP: {rec['src_fp']}")
            print(f"  LLM sink_is_FP:   {rec['sink_fp']}")
            print(f"  LLM explanation:  {rec['explanation'][:300]}...")

    # Show kept TPs for comparison
    if kept_tp:
        print(f"\n{'=' * 80}")
        print(f"KEPT TRUE POSITIVES — {len(kept_tp)} real vuln paths correctly kept")
        print(f"{'=' * 80}")
        for i, rec in enumerate(kept_tp[:5]):  # show first 5
            print(f"\n--- Kept TP #{i+1} (result={rec['result_id']}, flow={rec['code_flow_id']}) ---")
            print(f"  Source: {rec['source']}  [{rec['source_file']}]")
            print(f"  Sink:   {rec['sink']}  [{rec['sink_file']}]")
            print(f"  Matched fix method(s): {rec['matched_methods']}")
        if len(kept_tp) > 5:
            print(f"\n  ... and {len(kept_tp) - 5} more kept TPs")

    # Save JSON report
    report = {
        "project": project_slug,
        "run_id": run_id,
        "query": query,
        "summary": {
            "total_paths_analyzed": total,
            "parse_errors": parse_errors,
            "kept_tps": len(kept_tp),
            "killed_tps": len(killed_tp),
            "killed_fps": len(killed_fp),
            "kept_fps": len(kept_fp),
            "tp_kill_rate": round(len(killed_tp) / (len(killed_tp) + len(kept_tp)) * 100, 1) if (len(killed_tp) + len(kept_tp)) > 0 else 0,
        },
        "killed_tp_details": [
            {k: (list(v) if isinstance(v, set) else v) for k, v in rec.items()}
            for rec in killed_tp
        ],
        "kept_tp_details": [
            {k: (list(v) if isinstance(v, set) else v) for k, v in rec.items()}
            for rec in kept_tp
        ],
    }
    report_dir = f"{OUTPUT_DIR}/{project_slug}/{run_id}"
    report_path = f"{report_dir}/killed_tps_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
