/**
 * @name Local-user-controlled command line
 * @description Using externally controlled strings in a command line is vulnerable to malicious
 *              changes in the strings.
 * @kind path-problem
 * @problem.severity recommendation
 * @security-severity 9.8
 * @precision medium
 * @id java/mycommand-line-injection-local
 * @tags security
 *       external/cwe/cwe-078
 *       external/cwe/cwe-088
 */

import java
import MyCommandLineQuery
import MyExternalProcess
import MyLocalUserInputToArgumentToExecFlow::PathGraph

from
  MyLocalUserInputToArgumentToExecFlow::PathNode source,
  MyLocalUserInputToArgumentToExecFlow::PathNode sink, Expr e
where
  MyLocalUserInputToArgumentToExecFlow::flowPath(source, sink) and
  myargumentToExec(e, sink.getNode())
select e, source, sink, "This command line depends on a $@.", source.getNode(),
  "user-provided value"
