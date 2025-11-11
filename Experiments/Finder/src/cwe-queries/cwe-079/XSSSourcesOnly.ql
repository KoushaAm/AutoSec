/**
 * @name Cross-site scripting
 * @description Writing user input directly to a web page
 *              allows for a cross-site scripting vulnerability.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 6.1
 * @precision high
 * @id java/myxss-sources-only
 * @tags security
 *       external/cwe/cwe-079
 */

import java
import MyXssQuery
import MyXssFlowSourcesOnly::PathGraph

from MyXssFlowSourcesOnly::PathNode source, MyXssFlowSourcesOnly::PathNode sink
where MyXssFlowSourcesOnly::flowPath(source, sink)
select sink.getNode(), source, sink, "Cross-site scripting vulnerability due to a $@.",
  source.getNode(), "user-provided value"
