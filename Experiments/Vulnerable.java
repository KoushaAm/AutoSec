import java.util.Scanner;

// command line injection vulnerable class
public class Vulnerable {
    public static void main(String[] args) throws Exception {
        Scanner myObj = new Scanner(System.in);
        // potential source
        String userInput = myObj.nextLine();
        String cmd = "./mytool --version " + userInput;

        // potential sink
        Runtime.getRuntime().exec(cmd);
    }
}
