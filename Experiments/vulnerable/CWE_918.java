// CWE_918.java - minimal vulnerable example
import java.io.*;
import java.net.*;
import java.nio.charset.Charset;
import java.util.Base64;

public class CWE_918 {
    // VULNERABLE: treats Base64 as a "trusted encoding" and decodes into a URL/host
    public static String decodeHost(String host) {
        try {
            if (host == null || host.isBlank() || host.startsWith("http://") || host.startsWith("https://"))
                return host;
            return new String(Base64.getDecoder().decode(host), Charset.defaultCharset());
        } catch (Exception e) {
            return host;
        }
    }

    // VULNERABLE: simply Base64-encodes the (possibly attacker-supplied) host
    public static String encodeHost(String host) {
        try {
            if (!host.toLowerCase().startsWith("http"))
                host = "http://" + host;
            return Base64.getEncoder().encodeToString(host.getBytes(Charset.defaultCharset()));
        } catch (Exception e) {
            return host;
        }
    }

    // Sink: opens a connection to the decoded value (demonstrates SSRF)
    public static String fetch(String encodedOrPlain) {
        String target = decodeHost(encodedOrPlain);
        if (target == null) return null;
        try {
            URL url = new URL(target);
            URLConnection conn = url.openConnection();
            conn.setConnectTimeout(2000);
            conn.setReadTimeout(2000);
            try (InputStream in = conn.getInputStream()) {
                byte[] buf = new byte[128];
                int n = in.read(buf);
                return n > 0 ? new String(buf, 0, n, Charset.defaultCharset()) : "";
            }
        } catch (Exception e) {
            return "ERROR: " + e.getClass().getSimpleName() + ": " + e.getMessage();
        }
    }

    // Quick demo: encodes "localhost:7070", decodes it and fetches it.
    public static void main(String[] args) {
        String plain = "localhost:7070"; // change to any host to simulate (use isolated env)
        String encoded = encodeHost(plain);
        System.out.println("plain:   " + plain);
        System.out.println("encoded: " + encoded);
        System.out.println("decoded: " + decodeHost(encoded));
        System.out.println("fetch:   " + fetch(encoded));
    }
}
