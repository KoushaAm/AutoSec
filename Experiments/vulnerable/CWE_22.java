import java.io.File;

/**
 * Minimal vulnerable example for CWE-22 (Path Traversal).
 * https://cwe.mitre.org/data/definitions/22.html (example 4)
 *
 * Usage:
 *   // dry-run (safe)
 *   java CWE_22 /safe_dir/somefile.txt
 *
 * Attack example that bypasses naive startsWith:
 *   /safe_dir/../important.dat
 */
public class CWE_22 {
    public static void main(String[] args) {
        if (args.length == 0) {
            System.out.println("Usage: java CWE_22 <path>");
            return;
        }

        // >>> Vulnerable check: only checks string prefix
        String path = args[0];
        if (path.startsWith("/safe_dir/")) {
            File f = new File(path);
            f.delete();
        }
    }
}
