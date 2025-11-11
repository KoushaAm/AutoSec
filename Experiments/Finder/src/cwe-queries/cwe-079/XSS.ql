/**
 * @name Cross-site scripting
 * @description Writing user input directly to a web page
 *              allows for a cross-site scripting vulnerability.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 6.1
 * @precision high
 * @id java/myxss
 * @tags security
 *       external/cwe/cwe-079
 */

import java
import MyXssQuery
import MyXssFlow::PathGraph

bindingset[src]
string sourceType(DataFlow::Node src) {
  if exists(Parameter p | src.asParameter() = p)
  then result = "user-provided value as public function parameter"
  else result = "user-provided value from external api return value"
}

from MyXssFlow::PathNode source, MyXssFlow::PathNode sink
where MyXssFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "Cross-site scripting vulnerability due to a $@.",
  source.getNode(),
  sourceType(source.getNode())
