#!/usr/bin/env python3

"""
Generate Pipeline/project_variants.py from a CSV of AutoSec project slugs and CWEs.

Expected CSV columns:
    Project Slug
    CWE

Usage:
    python Pipeline/scripts/generate_project_variants.py AutoSec_120_Project_Variants.csv

Optional:
    python Pipeline/scripts/generate_project_variants.py AutoSec_120_Project_Variants.csv --output Pipeline/project_variants.py

Behavior:
    - Each CSV row becomes one ProjectVariants enum entry.
    - If a project has multiple CWEs, only the first CWE is used.
      Example: "CWE-022, CWE-020" -> "cwe-022"
    - Enum names are generated from the project slug and CVE.
    - dummy_finder_output paths are generated from the enum name.
    - dummy_exploiter_pov_logic is set to "..." as a placeholder.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


REQUIRED_COLUMNS = {"Project_Slug", "CWE"}


def normalize_primary_cwe(cwe_value: str) -> str:
    """
    Return only the first CWE as the primary cwe_id.

    Examples:
        "CWE-022"              -> "cwe-022"
        "CWE-022, CWE-020"     -> "cwe-022"
        "CWE-78, CWE-94"       -> "cwe-078"
        "NVD-CWE-noinfo"       -> "cwe-noinfo"
    """
    first_cwe = str(cwe_value).split(",")[0].strip()

    match = re.search(r"(\d+)", first_cwe)
    if match:
        return f"cwe-{match.group(1).zfill(3)}"

    return "cwe-noinfo"


def enum_name_from_project_slug(project_slug: str) -> str:
    """
    Convert a project slug into a stable Python enum name.

    Example:
        codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5
        -> CODEHAUS_PLEXUS_PLEXUS_ARCHIVER_CVE_2018_1002200
    """
    slug_before_version = project_slug

    cve_match = re.search(r"CVE-\d{4}-\d+", project_slug)
    if cve_match:
        cve_end = cve_match.end()
        slug_before_version = project_slug[:cve_end]

    enum_name = re.sub(r"[^A-Za-z0-9]+", "_", slug_before_version)
    enum_name = enum_name.strip("_").upper()

    if not enum_name:
        raise ValueError(f"Could not generate enum name from project slug: {project_slug}")

    if enum_name[0].isdigit():
        enum_name = f"P_{enum_name}"

    return enum_name


def read_project_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV appears to be empty or missing headers.")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                f"CSV is missing required columns: {sorted(missing_columns)}. "
                f"Found columns: {reader.fieldnames}"
            )

        rows: list[dict[str, str]] = []

        for line_number, row in enumerate(reader, start=2):
            project_slug = str(row.get("Project_Slug", "")).strip()
            cwe_value = str(row.get("CWE", "")).strip()

            if not project_slug:
                raise ValueError(f"Missing Project Slug at CSV line {line_number}")

            if not cwe_value:
                raise ValueError(f"Missing CWE at CSV line {line_number}")

            rows.append(
                {
                    "project_slug": project_slug,
                    "cwe_id": normalize_primary_cwe(cwe_value),
                    "enum_name": enum_name_from_project_slug(project_slug),
                }
            )

    return rows


def validate_unique_project_slugs(rows: list[dict[str, str]]) -> None:
    seen: dict[str, str] = {}

    for row in rows:
        project_slug = row["project_slug"]
        enum_name = row["enum_name"]

        if project_slug in seen:
            raise ValueError(f"Duplicate project slug found in CSV: {project_slug}")

        seen[project_slug] = enum_name


def validate_unique_enum_names(rows: list[dict[str, str]]) -> None:
    seen: dict[str, str] = {}

    for row in rows:
        enum_name = row["enum_name"]
        project_slug = row["project_slug"]

        if enum_name in seen:
            raise ValueError(
                "Generated duplicate enum name.\n"
                f"Enum name: {enum_name}\n"
                f"Project 1: {seen[enum_name]}\n"
                f"Project 2: {project_slug}\n"
                "Update enum_name_from_project_slug() to include more distinguishing information."
            )

        seen[enum_name] = project_slug


def render_project_variants_py(rows: list[dict[str, str]]) -> str:
    enum_entries: list[str] = []

    for row in rows:
        enum_name = row["enum_name"]
        project_slug = row["project_slug"]
        cwe_id = row["cwe_id"]

        enum_entries.append(
            f'''    {enum_name} = {{
        "name": "{project_slug}",
        "cwe_id": "{cwe_id}",
        "dummy_finder_output": "Projects/Finder_Output/{enum_name}.json",
        "dummy_exploiter_pov_logic": "..."
    }}'''
        )

    enum_body = "\n\n".join(enum_entries)

    return f'''# ====== Project Variants ======
# Auto-generated by Pipeline/scripts/generate_project_variants.py
# Do not manually edit generated entries. Update the CSV and regenerate instead.

from enum import Enum


class ProjectVariants(Enum):
{enum_body}

    @property
    def project_name(self) -> str:
        return self.value["name"]

    @property
    def cwe_id(self) -> str:
        return self.value["cwe_id"]

    @property
    def dummy_finder_output(self) -> str:
        return self.value["dummy_finder_output"]

    @property
    def dummy_exploiter_pov_logic(self) -> str | None:
        return self.value.get("dummy_exploiter_pov_logic")

    @classmethod
    def from_project_slug(cls, project_slug: str) -> "ProjectVariants":
        for variant in cls:
            if variant.project_name == project_slug:
                return variant

        raise ValueError(f"No ProjectVariants entry found for project slug: {{project_slug}}")

    @classmethod
    def by_cwe(cls, cwe_id: str) -> list["ProjectVariants"]:
        normalized_cwe_id = cwe_id.lower()
        return [variant for variant in cls if variant.cwe_id == normalized_cwe_id]

    @classmethod
    def valid_for_experiment(cls) -> list["ProjectVariants"]:
        return [
            variant
            for variant in cls
            if variant.cwe_id != "cwe-noinfo"
        ]
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Pipeline/project_variants.py from an AutoSec project variants CSV."
    )

    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the CSV file. Expected columns: Project Slug, CWE.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Pipeline/project_variants.py"),
        help="Output path for generated project_variants.py. Defaults to Pipeline/project_variants.py.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rows = read_project_rows(args.csv_path)
    validate_unique_project_slugs(rows)
    validate_unique_enum_names(rows)

    generated_content = render_project_variants_py(rows)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated_content, encoding="utf-8")

    noinfo_count = sum(1 for row in rows if row["cwe_id"] == "cwe-noinfo")

    print(f"Generated {args.output}")
    print(f"Project variants written: {len(rows)}")
    print(f"Projects with cwe-noinfo: {noinfo_count}")


if __name__ == "__main__":
    main()