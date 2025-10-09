(# Running Vulnerable.java)

This file shows minimal, exact steps to compile and run `Vulnerable.java` from the `Experiments` folder using a bash shell. It also includes a tiny dummy `mytool` you can create for testing and short troubleshooting notes.

## Quick steps

1. Compile the Java source, this generates `.class` files
```bash
javac Vulnerable.java
```

2. Run (interactive). The program reads one line from stdin, then runs an external command using that line:
```bash
java Vulnerable
# type a line and press Enter when the program waits for input
```

3. Run non-interactively (pipe a single line as input):
```bash
echo "echo someInput" | java Vulnerable
```

## Quick Remove .class files
- `rm -rf *.class`