/**
 * @name Server-side template injection
 * @description Untrusted input interpreted as a template can lead to remote code execution.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 9.3
 * @precision high
 * @id java/my-server-side-template-injection
 * @tags security
 *       external/cwe/cwe-1336
 *       external/cwe/cwe-094
 */

 import java
 import MyTemplateInjectionQuery
 import MyTemplateInjectionFlow::PathGraph
 
 from MyTemplateInjectionFlow::PathNode source, MyTemplateInjectionFlow::PathNode sink
 where MyTemplateInjectionFlow::flowPath(source, sink)
 select sink.getNode(), source, sink, "Template, which may contain code, depends on a $@.",
   source.getNode(), "user-provided value"
 