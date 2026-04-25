# ====== Project Variants ======
from enum import Enum

class ProjectVariants(Enum):
    CODEHAUS_CVE_2018_1002200 = {
        "name": "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output/CODEHAUS_CVE_2018_1002200.json",
        "dummy_exploiter_pov_logic": "A JUnit test creates a ZIP with an entry whose name contains ../ sequences (\"../../../../pwned_by_zip_slip.txt\"). The test uses the project's public ZipUnArchiver API to extract the archive to a destination directory. Because the library resolves the entry name into a File without normalizing/sanitizing traversal components, extraction writes a file outside the intended destination (pwned_by_zip_slip.txt). The test detects this external file, prints the required AUTOSEC_POV_TRIGGERED marker and fails, proving the vulnerability is exploitable."
    }
    CODEHAUS_CVE_2017_1000487 = {
        "name": "codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15",
        "cwe_id": "cwe-078",
        "dummy_finder_output": "Projects/Finder_Output/CODEHAUS_CVE_2017_1000487.json",
        "dummy_exploiter_pov_logic": "The proof-of-violation JUnit test constructs a Commandline using BourneShell, sets the executable to crafted inputs (payloads that include backticks, $(), or strings that start/end with quote characters) and calls Commandline.execute(). Because the vulnerable code path appends the executable into a single shell command string using StringUtils.quoteAndEscape, certain crafted inputs are not properly escaped/quoted and reach the shell interpreter. The test verifies exploitation by observing a side-effect: creation of a file (touch pwned_by_exploit.txt). If the file is created the test prints and fails with the required marker \"AUTOSEC_POV_TRIGGERED\" — demonstrating command injection at runtime."
    }
    ESAPI_CVE_2022_23457 = {
        "name": "ESAPI__esapi-java-legacy_CVE-2022-23457_2.2.3.1",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output/ESAPI_CVE_2022_23457.json",
        "dummy_exploiter_pov_logic": "The PoV creates two directories under the system temp directory: a parent (/tmp/esapi_parent_test) and a sibling trick directory (/tmp/esapi_parent_test_trick) whose canonical path begins with the parent's canonical path. It writes an ESAPI-style XML config containing the trick directory absolute path and loads it via XmlEsapiPropertyLoader (the reported source: new File(filename) in AbstractPrioritizedPropertyLoader). The loaded property value is then passed to DefaultValidator.getValidDirectoryPath(context, value, parent, false). If the startsWith check permitted the trick directory and the canonical-equals-input check did not block it, the validator would accept the trick directory and the test would print and fail with the exact marker AUTOSEC_POV_TRIGGERED. In runtime testing the validator rejected the trick directory (threw ValidationException), so the PoV did not trigger; thus the practical exploit attempt failed in this environment. The likely reason is the canonical-equals-input check (via fileValidator.getValidInput on the canonical path / the DirectoryName rule) produced a canonical value that did not equal the provided input, preventing the bypass even though startsWith(parentCanonical) returned true."
    }
    KUBERNETES_CLIENT_CVE_2020_8570 = {
        "name": "kubernetes-client__java_CVE-2020-8570_client-java-parent-9.0.1",
        "cwe_id": "cwe-022", # Both CWE-22 & CWE-23
        "dummy_finder_output": "Projects/Finder_Output/KUBERNETES_CLIENT_CVE_2020_8570.json",
        "dummy_exploiter_pov_logic": "The PoV subclasses Copy and overrides exec(...) to return a fake Process whose input stream is a base64-encoded gzipped tar containing an archive entry with a traversal path (e.g., \"../../../../../../tmp/AUTOSEC_POV\"). copyDirectoryFromPod decodes the stream, iterates archive entries and constructs target File objects by directly concatenating the destination directory with entry.getName() without normalization. The test then checks for creation of /tmp/AUTOSEC_POV; if present it prints and fails with the marker AUTOSEC_POV_TRIGGERED, proving that an archive entry can cause files to be written outside the intended destination."
    }
    PERWENDEL_CVE_2016_9177 = {
        "name": "perwendel__spark_CVE-2016-9177_2.5.1",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output/PERWENDEL_CVE_2016_9177.json",
        "dummy_exploiter_pov_logic": "A JUnit PoV test was added that writes a sentinel file at /tmp/AUTOSEC_SECRET and constructs an HTTP request shape that supplies a servletPath/pathInfo containing '..' traversal attempts. The test invokes the project's ExternalResourceHandler code path (via handler.getResource(request) and ultimately ExternalResource.getInputStream()). Instrumentation added to ExternalResourceHandler showed UriPath.canonical(...) returned null for the composed incoming path containing '..', causing the handler to fall back to the base resource path and return no existing resource. The test attempted to read the resource and would have printed and failed with the marker 'AUTOSEC_POV_TRIGGERED' if the secret had been read, but it did not. Therefore the attempted traversal is prevented by UriPath.canonical and the FileInputStream sink is not reached for the crafted input."
    }
    RHUSS_CVE_2018_1000129 = {
        "name": "rhuss__jolokia_CVE-2018-1000129_1.4.0",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output/RHUSS_CVE_2018_1000129.json",
        "dummy_exploiter_pov_logic": "A TestNG PoV was implemented that initializes AgentServlet, mocks an HttpServletRequest returning ConfigKey.STREAMING='true' and a malicious callback payload (</script><script>...)</script> and then calls servlet.doGet(request,response). The test captures the servlet output stream and checks whether the raw payload appears. If the raw payload is present the test prints and fails with the marker AUTOSEC_POV_TRIGGERED. During execution the test could not complete the dynamic verification because servlet.init triggered backend initialization that invoked ServletContext.log(String, Throwable). The EasyMock servlet context in the test did not accept that unexpected two-arg log call (causing an assertion and aborting before doGet). Despite the failed dynamic attempt, static analysis of the code path shows the callback parameter is written to the response without escaping on both streaming (IoUtil.pWriter.write(callback)) and non-streaming (concatenated callback + '(' + json + ');' then out.write) paths, which constitutes an XSS vector for JSONP callbacks."
    }
    SPRING_CLOUD_CVE_2022_22947 = {
        "name": "spring-cloud__spring-cloud-gateway_CVE-2022-22947_3.0.6",
        "cwe_id": "cwe-094", # Both CWE-94 & CWE-917
        "dummy_finder_output": "Projects/Finder_Output/SPRING_CLOUD_CVE_2022_22947.json",
        "dummy_exploiter_pov_logic": "A PoV Spring Boot test application was started that registers the MVC ProxyExchangeArgumentResolver and configures the auto-forwarded headers to include an attacker-controlled header name (\"X-Exploit\"). The test issues a proxied request to the application's /proxy endpoint with the header name present. The downstream echoed endpoint observed the propagated header name, the test printed the required marker \"AUTOSEC_POV_TRIGGERED\" and failed — demonstrating that untrusted header names from the incoming HttpServletRequest were added into the proxied HttpHeaders and reached downstream code, confirming the code-injection-related propagation path at runtime."
    }
    WHITESOURCE_CVE_2022_23082 = {
        "name": "whitesource__curekit_CVE-2022-23082_1.1.3",
        "cwe_id": "cwe-022",
        "dummy_finder_output": "Projects/Finder_Output/WHITESOURCE_CVE_2022_23082.json",
        "dummy_exploiter_pov_logic": "The PoV creates two sibling directories in the system temp directory: a legitimate base directory and an 'evil' directory whose pathname begins with the base directory's name (prefix collision). It writes a file into the evil directory and calls FileSecurityUtils.isFileOutsideDir(filePath, baseDirPath). Because the implementation uses String.startsWith on canonical paths without ensuring a path separator boundary, the evil file's canonical path will share the base directory string prefix, causing startsWith to return true and the method to incorrectly report the file as inside the base dir. The PoV fails the test and prints AUTOSEC_POV_TRIGGERED when this incorrect behavior is observed."
    }
    XUXUELI_CVE_2020_29204 = {
        "name": "xuxueli__xxl-job_CVE-2020-29204_2.2.0",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output/XUXUELI_CVE_2020_29204.json",
        "dummy_exploiter_pov_logic": "The PoV exercises the actual controller code path: send an HTTP POST to /user/add with a username containing a script payload that satisfies the controller's length check (4-20 chars). The controller trims and validates the username and persists it via the DAO. A subsequent GET to /user/pageList returns the persisted XxlJobUser objects inside the 'data' JSON field. The client-side user.index.1.js populates table cells from that JSON without escaping, so a stored payload in username will be inserted into the page DOM and executed. The test attempts to trigger this by mocking the DAO to capture the saved user and returning it from pageList, then failing the test (and printing AUTOSEC_POV_TRIGGERED) if the raw script payload is present in the /user/pageList JSON response."
    }
    NAHSRA_CVE_2016_10006 = {
        "name": "nahsra__antisamy_CVE-2016-10006_1.5.3",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output/NAHSRA_CVE_2016_10006.json",
        "dummy_exploiter_pov_logic": "..."
    }
    NAHSRA_CVE_2022_29577 = {
        "name": "nahsra__antisamy_CVE-2022-29577_1.6.6.1",
        "cwe_id": "cwe-079",
        "dummy_finder_output": "Projects/Finder_Output/NAHSRA_CVE_2022_29577.json",
        "dummy_exploiter_pov_logic": "..."
    }

    # TODO: delete scripts below after experimentation complete
    # sudo python scripts/fetch_one.py <project name>
    # sudo python Pipeline/convert_to_finder_output.py kubernetes-client__java_CVE-2020-8570_client-java-parent-9.0.1 cwe-022 KUBERNETES_CLIENT_CVE_2020_8570.json
    # chmod -R u+w Projects/Sources/spring-cloud__spring-cloud-gateway_CVE-2022-22947_3.0.6/
    # cd Agents/Exploiter/data/cwe-bench-java/workdir_no_branch/project-sources/
    WILDFLY_2018 = {
        "name" : "wildfly__wildfly_CVE-2018-1047_11.0.0.Final",
        "cwe_id": "cwe-022"
    }

    APACHE_MYFACES = {
        "name": "apache__myfaces_CVE-2011-4367_2.0.11",
        "cwe_id": "cwe-022"
    }

    APACHE_SLING = {
        "name": "apache__sling-org-apache-sling-servlets-resolver_CVE-2024-23673_2.10.0",
        "cwe_id": "cwe-022"
    }

    XERIAL_SQLITE = {
        "name": "xerial__sqlite-jdbc_CVE-2023-32697_3.41.2.1",
        "cwe_id": "cwe-094"
    }

    ASF_CXF = {
        "name": "asf__cxf_CVE-2016-6812_3.0.11",
        "cwe_id": "cwe-079"
    }

    APACHE_MINA = {
        "name": "apache__mina-sshd_CVE-2023-35887_2.9.2",
        "cwe_id": "cwe-022"
    }

    ASF_TAPESTRY = {
        "name": "asf__tapestry-5_CVE-2019-0207_5.4.4",
        "cwe_id": "cwe-022"
    }

    APACHE_TIKA = {
        "name": "apache__tika_CVE-2018-11762_1.18",
        "cwe_id": "cwe-022"
    }

    ZERO_TURNAROUND = {
        "name": "zeroturnaround__zt-zip_CVE-2018-1002201_1.12",
        "cwe_id": "cwe-022"
    }

    DIFFPLUG_GOOMPH = {
        "name": "diffplug__goomph_CVE-2022-26049_3.37.1",
        "cwe_id": "cwe-022"
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