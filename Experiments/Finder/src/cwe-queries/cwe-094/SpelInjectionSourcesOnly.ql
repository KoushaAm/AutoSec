/**
 * @name Expression language injection (Spring)
 * @description Evaluation of a user-controlled Spring Expression Language (SpEL) expression
 *              may lead to remote code execution.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 9.3
 * @precision high
 * @id java/my-spel-expression-injection-sinks-only
 * @tags security
 *       external/cwe/cwe-094
 */

 import java
 import MySpelInjectionQuery
 import semmle.code.java.dataflow.DataFlow
 import MySpelInjectionFlowSourcesOnly::PathGraph
 
 from MySpelInjectionFlowSourcesOnly::PathNode source, MySpelInjectionFlowSourcesOnly::PathNode sink
 where MySpelInjectionFlowSourcesOnly::flowPath(source, sink)
 select sink.getNode(), source, sink, "SpEL expression depends on a $@.", source.getNode(),
   "user-provided value"
 