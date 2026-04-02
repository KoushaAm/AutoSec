from pathlib import Path
import csv

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = SCRIPT_DIR.parent / "iclr-2025-results" / "IRIS+GPT-4-v1.csv"

with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)

    fdr_values_from_counts = []
    fdr_values_from_precision = []

    for i, row in enumerate(reader, start=1):
        paths = float(row["Alerts"])
        if paths == 0:
            continue

        tp_paths = float(row["TP Alerts"])
        precision_csv = float(row["Precision"])

        fdr_counts = 1 - (tp_paths / paths)
        fdr_precision = 1 - precision_csv

        fdr_values_from_counts.append(fdr_counts)
        fdr_values_from_precision.append(fdr_precision)

        if abs(fdr_counts - fdr_precision) > 1e-9:
            print(f"Mismatch on row {i}: {row.get('CVE')}")
            print(f"  from counts   = {fdr_counts}")
            print(f"  from precision= {fdr_precision}")

    avg_counts = sum(fdr_values_from_counts) / len(fdr_values_from_counts)
    avg_precision = sum(fdr_values_from_precision) / len(fdr_values_from_precision)

    print(f"Avg FDR from Paths/TP Paths: {avg_counts * 100:.2f}%")
    print(f"Avg FDR from Precision col : {avg_precision * 100:.2f}%")