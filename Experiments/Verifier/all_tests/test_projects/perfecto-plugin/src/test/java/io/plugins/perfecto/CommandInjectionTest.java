/*
package io.plugins.perfecto;

import org.junit.jupiter.api.Test;
import java.lang.reflect.Field;
import java.util.regex.Pattern;
import java.util.*;

public class CommandInjectionTest {
    @Test
    public void testCommandInjection() {
        List<String> inputs = Arrays.asList("safe_input", "allowed.chars_123", "malicious;cmd");
        String[] cmdArgs;
        try {
            cmdArgs = getCmdArgs();
        } catch (Exception e) {
            fail("Failed to retrieve cmd args: " + e.getMessage());
        }

        for (String input : inputs) {
            setInput(input);
            String[] args = getCmdArgs();
            boolean exploitable = false;
            for (String arg : args) {
                if (!Pattern.matches("^[A-Za-z0-9._-]+$", arg)) {
                    exploitable = true;
                    break;
                }
            }
            writeReport(input, exploitable ? "YES" : "NO");
        }
    }

    private String[] getCmdArgs() throws Exception {
        PerfectoBuildWrapper wrapper = new PerfectoBuildWrapper();
        Field cmdArgsField = wrapper.getClass().getDeclaredField("cmdArgs");
        cmdArgsField.setAccessible(true);
        return (String[]) cmdArgsField.get(wrapper);
    }

    private void setInput(String input) {
        PerfectoCredentials cred = new PerfectoCredentials();
        cred.setName(input);
        PerfectoBuildWrapper wrapper = new PerfectoBuildWrapper(cred);
    }

    private void writeReport(String input, String exploitable) {
        StringBuilder report = new StringBuilder();
        report.append("Vulnerability Rule ID: java/my-command-line-injection-extra\n");
        report.append("CWE ID: 78\n");
        report.append("InputsTested: [ \"").append(input).append("\" ]\n");
        report.append("Exploitable: ").append(exploitable).append("\n");
        report.append("Rationale: Untrusted input directly used in command construction without sanitization.\n");
        report.append("Procedure: Tested by injecting various inputs into credentials name.\n");

        Write("test-harness/report.txt", report.toString());
    }
}
*/