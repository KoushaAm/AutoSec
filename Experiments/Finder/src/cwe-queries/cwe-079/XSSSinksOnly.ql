/**
 * @name Cross-site scripting
 * @description Writing user input directly to a web page
 *              allows for a cross-site scripting vulnerability.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 6.1
 * @precision high
 * @id java/myxss-sinks-only
 * @tags security
 *       external/cwe/cwe-079
 */

import java
import MyXssQuery
import MyXssFlowSinksOnly::PathGraph

from MyXssFlowSinksOnly::PathNode source, MyXssFlowSinksOnly::PathNode sink
where MyXssFlowSinksOnly::flowPath(source, sink)
select sink.getNode(), source, sink, "Cross-site scripting vulnerability due to a $@.",
  source.getNode(), "user-provided value"
