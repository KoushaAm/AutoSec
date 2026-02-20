# ====== Project Variants ======
from enum import Enum

class ProjectVariants(Enum):
    CODEHAUS_2018 = {
        "name": "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5",
        "cwe_id": "cwe-022"
    }
    CODEHAUS_2017 = {
        "name": "codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15",
        "cwe_id": "cwe-078"
    }
    NAHSRA = {
        "name": "nahsra__antisamy_CVE-2016-10006_1.5.3",
        "cwe_id": "cwe-079"
    }
    PERWENDEL_2018 = {
        "name": "perwendel__spark_CVE-2018-9159_2.7.1",
        "cwe_id": "cwe-022"
    }
    # Primary 5 Experiments below
    DSPACE = {
        "name": "DSpace__DSpace_CVE-2022-31192_5.10",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output_JSON/finder_output_dspace.json",
        "dummy_exploiter_pov_logic": "The PoV set the configured export base dir to /tmp/export, created an external sentinel file at /tmp/secret_outside/secret_1.zip, constructed an EPerson with an id (100) and invoked ItemExport.getExportDownloadInputStream(...) with a traversal payload \"../../secret_outside/secret_1.zip\". The method concatenates the attacker-controlled filename onto the configured directory without normalization and opened a FileInputStream on the resulting File. The test read the external sentinel contents, printed the required marker (AUTOSEC_POV_TRIGGERED) and failed the test, demonstrating an end-to-end exploit of the path traversal vulnerability"
    }
    KUBERNETES_CLIENT = {
        "name": "kubernetes-client__java_CVE-2020-8570_client-java-parent-9.0.1",
        "cwe_id": "cwe-022", # multiple CWEs possible based on SARIF
        "dummy_finder_output": "Projects/Finder_Output_JSON/finder_output_kubernetes.json",
        "dummy_exploiter_pov_logic": "A JUnit PoV was created that constructs a base64-encoded gzipped tar containing malicious entries (absolute path and deep '../' traversal). The test overrides Copy.exec(...) to return a Process whose stdout is the crafted archive (matching the exec path the library uses), then calls copy.copyDirectoryFromPod(...). After extraction the test checks for creation of /tmp/AUTOSEC_POV_TRIGGERED.txt and would print and fail with the required marker if observed. The PoV could not be confirmed: Maven test compilation failed initially with a missing-symbol error for a helper method; the helper was later added under autosec/tests but the container test run continued to report the same compile error and the run did not produce the AUTOSEC_POV_TRIGGERED marker. Therefore exploitability in this repository/version was not verified at runtime."
    }
    PERFECTO_PLUGIN = {
        "name": "jenkinsci__perfecto-plugin_CVE-2020-2261_1.17",
        "cwe_id": "cwe-078",
        "dummy_finder_output": "Projects/Finder_Output_JSON/finder_output_perfecto.json",
        "dummy_exploiter_pov_logic": "No PoV Logic available yet" # TODO: add PoV logic when accessible
    }
    WHITESOURCE = {
        "name": "whitesource__curekit_CVE-2022-23082_1.1.3",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/finder_output_whitesource.json",
        "dummy_exploiter_pov_logic": "The PoV creates two directories: /tmp/cure_base (intended base) and /tmp/cure_base_trick (an outside directory whose path begins with the base's pathname). A file is placed in /tmp/cure_base_trick/outside.txt and passed as filePath while baseDir is /tmp/cure_base. Because the implementation uses startsWith on the canonical paths, \"/tmp/cure_base_trick\".startsWith(\"/tmp/cure_base\") evaluates to true, causing isFileOutsideDir to return false (i.e. treated as inside) even though the file is outside. The test prints \"AUTOSEC_POV_TRIGGERED\" and fails when this incorrect behavior is observed, proving the vulnerability is exploitable."
    }
    YAMCS = {
        "name": "yamcs__yamcs_CVE-2023-45277_5.8.6",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/finder_output_yamcs.json",
        "dummy_exploiter_pov_logic": "No PoV Logic available yet" # TODO: add PoV logic when accessible
    }


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
    def dummy_exploiter_pov_logic(self) -> str:
        return self.value["dummy_exploiter_pov_logic"]