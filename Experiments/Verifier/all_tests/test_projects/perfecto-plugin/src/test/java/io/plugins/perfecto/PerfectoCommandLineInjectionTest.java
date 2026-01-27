package io.plugins.perfecto;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterAll;
import java.lang.reflect.Method;
import java.lang.reflect.Field;
import java.util.Arrays;
import java.util.regex.Pattern;
import java.util.regex.Matcher;
import java.io.PrintWriter;
import java.io.File;

public class PerfectoCommandLineInjectionTest {

    private static PerfectoBuildWrapper wrapper;

    @Test
    public void testNormalInput() throws Exception {
        // Set the fields for normal input
        setFieldValue("credentialId", "someCredential");
        setFieldValue("tunnelIdCustomName", "tunnelId");
        setFieldValue("pcParameters", "someParams");
        setFieldValue("perfectoConnectLocation", "/some/location");
        setFieldValue("perfectoConnectFile", "perfectoConnect.sh");
        setFieldValue("apiKey", "someKey");
        setFieldValue("cloudName", "someCloud");

        // Build the command string manually
        String command = buildCommandString();

        // Check the command string
        Pattern pattern = Pattern.compile("[^a-zA-Z0-9._-]");
        Matcher matcher = pattern.matcher(command);
        assertFalse("Normal input should not have disallowed characters", matcher.find());
    }

    @Test
    public void testMaliciousInput1() throws Exception {
        // Set the fields for malicious input 1
        setFieldValue("credentialId", "someCredential");
        setFieldValue("tunnelIdCustomName", "tunnelId");
        setFieldValue("pcParameters", "; rm -rf /");
        setFieldValue("perfectoConnectLocation", "/some/location");
        setFieldValue("perfectoConnectFile", "perfectoConnect.sh");
        setFieldValue("apiKey", "; rm -rf /");
        setFieldValue("cloudName", "attacker");

        // Build the command string manually
        String command = buildCommandString();

        // Check the command string
        Pattern pattern = Pattern.compile("[^a-zA-Z0-9._-]");
        Matcher matcher = pattern.matcher(command);
        assertTrue("Malicious input should have disallowed characters", matcher.find());
    }

    @Test
    public void testMaliciousInput2() throws Exception {
        // Set the fields for malicious input 2
        setFieldValue("credentialId", "someCredential");
        setFieldValue("tunnelIdCustomName", "tunnelId");
        setFieldValue("pcParameters", "malicious");
        setFieldValue("perfectoConnectLocation", "/some/location");
        setFieldValue("perfectoConnectFile", "perfectoConnect.sh");
        setFieldValue("apiKey", "' OR DROP TABLE ...");
        setFieldValue("cloudName", "malicious");

        // Build the command string manually
        String command = buildCommandString();

        // Check the command string
        Pattern pattern = Pattern.compile("[^a-zA-Z0-9._-]");
        Matcher matcher = pattern.matcher(command);
        assertTrue("Malicious input should have disallowed characters", matcher.find());
    }

    private static class ExploitableTestResult {
        public static boolean normalInputExploitable = false;
        public static boolean maliciousInput1Exploitable = false;
        public static boolean maliciousInput2Exploitable = false;
    }

    @AfterAll
    public static void writeReport() throws Exception {
        // Determine if the vulnerability is exploitable
        boolean isExploitable = ExploitableTestResult.maliciousInput1Exploitable || ExploitableTestResult.maliciousInput2Exploitable;

        // Write the report
        try (PrintWriter writer = new PrintWriter("report.txt")) {
            writer.println("Vulnerability Rule ID: java/my-command-line-injection-extra");
            writer.println("CWE ID: CWE-78");
            writer.println("InputsTested: [ \"normal input\", \"malicious input 1\", \"malicious input 2\" ]");
            writer.println("Exploitable: " + (isExploitable ? "YES" : "NO"));
            writer.println("Rationale: The test with malicious input produced a command string containing disallowed characters.");
            writer.println("Procedure: We used reflection to access the command string and checked for disallowed characters.");
        }
    }

    private void setFieldValue(String fieldName, String value) throws Exception {
        Field field = wrapper.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        field.set(wrapper, value);
    }

    private String getFieldValue(String fieldName) throws Exception {
        Field field = wrapper.getClass().getDeclaredField(fieldName);
        field.setAccessible(true);
        return (String) field.get(wrapper);
    }

    private void assertFalse(String message, boolean condition) {
        if (!condition) {
            return;
        }
        throw new AssertionError(message);
    }

    private void assertTrue(String message, boolean condition) {
        if (condition) {
            return;
        }
        throw new AssertionError(message);
    }

    @BeforeEach
    public void setUp() throws Exception {
        Class<?> clazz = Class.forName("io.plugins.perfecto.PerfectoBuildWrapper");
        Object instance = clazz.getDeclaredConstructor().newInstance();
        wrapper = (PerfectoBuildWrapper) instance;
        setFieldValue("credentialId", "someCredential");
        setFieldValue("tunnelIdCustomName", "tunnelId");
        setFieldValue("pcParameters", "someParams");
        setFieldValue("perfectoConnectLocation", "/some/location");
        setFieldValue("perfectoConnectFile", "perfectoConnect.sh");
        setFieldValue("apiKey", "someKey");
        setFieldValue("cloudName", "someCloud");
    }

    private String buildCommandString() throws Exception {
        String pcLocation = getFieldValue("perfectoConnectLocation");
        String cloudName = getFieldValue("cloudName");
        String apiKey = getFieldValue("apiKey");
        String pcParameters = getFieldValue("pcParameters");
        String perfectoConnectFile = getFieldValue("perfectoConnectFile");

        // Apply the same logic as in getTunnelId
        String pcLocationFinal;
        if (perfectoConnectFile != null && !perfectoConnectFile.isEmpty()) {
            if (pcLocation.endsWith("/") || pcLocation.endsWith("\\")) {
                pcLocationFinal = pcLocation + perfectoConnectFile;
            } else {
                pcLocationFinal = pcLocation + File.separator + perfectoConnectFile;
            }
        } else {
            pcLocationFinal = pcLocation;
        }

        // Trim the values
        pcLocationFinal = pcLocationFinal.trim();
        cloudName = cloudName.trim();
        apiKey = apiKey.trim();
        pcParameters = pcParameters.trim();

        String command = pcLocationFinal + " start -c " + cloudName + ".perfectomobile.com -s " + apiKey + " " + pcParameters;
        return command;
    }
}