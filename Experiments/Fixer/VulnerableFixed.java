import java.util.Scanner;

// command line injection vulnerable class
public class VulnerableFixed {
    public static void main(String[] args) throws Exception {
        Scanner myObj = new Scanner(System.in);
        // potential source
        String userInput = myObj.nextLine().trim();

        // Validate user input with a conservative whitelist. Only allow
        // alphanumerics, dot, underscore and dash. Reject anything else.
        // If you have a small set of allowed flags, use a whitelist set instead.
        if (!userInput.isEmpty() && !userInput.matches("^[A-Za-z0-9_.-]+$")) {
            System.err.println("Invalid input - contains disallowed characters. Aborting.");
            return;
        }

        // Build the command as separate arguments (no shell parsing).
        // This avoids command-line injection because the input is passed
        // as an argument instead of being interpolated into a shell string.
        java.util.List<String> cmdList = new java.util.ArrayList<>();
        cmdList.add("java");
        cmdList.add("-version");
        if (!userInput.isEmpty()) cmdList.add(userInput);

        System.out.println("Executing: " + String.join(" ", cmdList));

        ProcessBuilder pb = new ProcessBuilder(cmdList);
        pb.redirectErrorStream(true);
        Process p = pb.start();

        // Print process output (stdout + stderr)
        try (java.io.BufferedReader reader = new java.io.BufferedReader(
                new java.io.InputStreamReader(p.getInputStream()))) {
            String line;
            while ((line = reader.readLine()) != null) {
                System.out.println(line);
            }
        }
        p.waitFor();
    }
}
