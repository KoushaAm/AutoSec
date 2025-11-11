/**
 * @name Command Injection into Runtime.exec() with dangerous command
 * @description High sensitvity and precision version of java/command-line-injection, designed to find more cases of command injection in rare cases that the default query does not find
 * @kind path-problem
 * @problem.severity error
 * @security-severity 6.1
 * @precision high
 * @id java/my-command-line-injection-extra-local
 * @tags security
 *       experimental
 *       local
 *       external/cwe/cwe-078
 */

import MyCommandInjectionRuntimeExec
import MyExecUserFlow::PathGraph

class LocalSource extends Source instanceof LocalUserInput { }

bindingset[src]
string sourceType(DataFlow::Node src) {
  if exists(Parameter p | src.asParameter() = p)
  then result = "user-provided value as public function parameter"
  else result = "user-provided value from external api return value"
}

from
  MyExecUserFlow::PathNode source,
  MyExecUserFlow::PathNode sink
  //, DataFlow::Node sourceCmd,    DataFlow::Node sinkCmd
where
  MyExecUserFlow::flowPath(source, sink)
  // where mycallIsTaintedByUserInputAndDangerousCommand(source, sink, sourceCmd, sinkCmd)
select sink, source, sink,
  "Call to dangerous java.lang.Runtime.exec() with command '$@' with arg from untrusted input",
  source.getNode(),
  sourceType(source.getNode())
