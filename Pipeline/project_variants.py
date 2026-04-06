# ====== Project Variants ======
from enum import Enum

class ProjectVariants(Enum):
    CODEHAUS_CVE_2018_1002200 = {
        "name": "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    CODEHAUS_CVE_2017_1000487 = {
        "name": "codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15",
        "cwe_id": "cwe-078",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    ESAPI_CVE_2022_23457 = {
        "name": "ESAPI__esapi-java-legacy_CVE-2022-23457_2.2.3.1",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    KUBERNETES_CLIENT_CVE_2020_8570 = {
        "name": "kubernetes-client__java_CVE-2020-8570_client-java-parent-9.0.1",
        "cwe_id": "cwe-022", # Both CWE-22 & CWE-23
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    PERWENDEL_CVE_2016_9177 = {
        "name": "perwendel__spark_CVE-2016-9177_2.5.1",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    RHUSS_CVE_2018_1000129 = {
        "name": "rhuss__jolokia_CVE-2018-1000129_1.4.0",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    SPRING_CLOUD = {
        "name": "spring-cloud__spring-cloud-gateway_CVE-2022-22947_3.0.6",
        "cwe_id": "cwe-094", # Both CWE-94 & CWE-917
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    WHITESOURCE_CVE_2022_23082 = {
        "name": "whitesource__curekit_CVE-2022-23082_1.1.3",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    XUXUELI_CVE_2020_29204 = {
        "name": "xuxueli__xxl-job_CVE-2020-29204_2.2.0",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output_JSON/...",
        "dummy_exploiter_pov_logic": "..."
    }
    # sudo python scripts/fetch_one.py <project name>
    # sudo python Pipeline/convert_to_finder_output.py <project-name> cwe-<id> <project-name>.json

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