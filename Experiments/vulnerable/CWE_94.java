import javax.servlet.ServletException;
import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import javax.script.ScriptEngine;
import javax.script.ScriptEngineManager;
import javax.script.ScriptException;

public class CWE_94 extends HttpServlet {

    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws ServletException, IOException {

        // User input is taken directly from a request parameter
        String formula = request.getParameter("formula"); 
        
        ScriptEngineManager manager = new ScriptEngineManager();
        ScriptEngine engine = manager.getEngineByName("JavaScript");

        try {
            // The user input is evaluated directly as code!
            Object result = engine.eval(formula); // CWE-94 vulnerability
            response.getWriter().println("Result: " + result);
        } catch (ScriptException e) {
            response.getWriter().println("Error: Invalid formula");
        }
    }
}
