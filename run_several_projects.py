import subprocess
import sys
from Pipeline.project_variants import ProjectVariants

projects = [ProjectVariants.PERWENDEL_2016]

for project in projects:
    try:
        subprocess.run(
            [sys.executable, "main.py", "--project", project.name],
            check=True
        )

        # get pre-filter
        subprocess.run(
            [
                sys.executable,
                "Pipeline/convert_to_finder_output.py",
                project.value["name"],
                project.value["cwe_id"],
                f"finder_output_{project.name}_pre_filter_modified_prompt.json",
            ],
            check=True
        )

        # get post-filter
        subprocess.run(
            [
                sys.executable,
                "Pipeline/convert_to_finder_output.py",
                project.value["name"],
                project.value["cwe_id"],
                f"finder_output_{project.name}_post_filter_modified_prompt.json",
                "--post_filter",
            ],
            check=True
        )

    except subprocess.CalledProcessError as e:
        print(f"pipeline for {project.name} failed")
        print("Return code:", e.returncode)