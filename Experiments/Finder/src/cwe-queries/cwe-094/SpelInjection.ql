/**
 * @name Expression language injection (Spring)
 * @description Evaluation of a user-controlled Spring Expression Language (SpEL) expression
 *              may lead to remote code execution.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 9.3
 * @precision high
 * @id java/my-spel-expression-injection
 * @tags security
 *       external/cwe/cwe-094
 */

import java
import MySpelInjectionQuery
import semmle.code.java.dataflow.DataFlow
import MySpelInjectionFlow::PathGraph

bindingset[src]
string sourceType(DataFlow::Node src) {
  if exists(Parameter p | src.asParameter() = p)
  then result = "user-provided value as public function parameter"
  else result = "user-provided value from external api return value"
}

from
  MySpelInjectionFlow::PathNode source,
  MySpelInjectionFlow::PathNode sink
where
  MySpelInjectionFlow::flowPath(source, sink)
select
  sink.getNode(), source, sink,
  "SpEL expression depends on a $@.", source.getNode(),
  sourceType(source.getNode())
