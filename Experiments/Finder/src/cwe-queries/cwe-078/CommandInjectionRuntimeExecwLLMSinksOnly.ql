/**
 * @name Command Injection into Runtime.exec() with dangerous command
 * @description High sensitvity and precision version of java/command-line-injection, designed to find more cases of command injection in rare cases that the default query does not find
 * @kind path-problem
 * @problem.severity error
 * @security-severity 6.1
 * @precision high
 * @id java/my-command-line-injection-extra
 * @tags security
 *       experimental
 *       external/cwe/cwe-078
 */

 import MyCommandInjectionRuntimeExec
 import MyExecUserFlowSinksOnly::PathGraph
 
 
 from
   MyExecUserFlowSinksOnly::PathNode source, MyExecUserFlowSinksOnly::PathNode sink
   //, DataFlow::Node sourceCmd,   DataFlow::Node sinkCmd
   where  MyExecUserFlowSinksOnly::flowPath(source, sink)
// where mycallIsTaintedByUserInputAndDangerousCommand(source, sink, sourceCmd, sinkCmd)
 select sink, source, sink,
   "Call to dangerous java.lang.Runtime.exec() with command '$@' with arg from untrusted input",
   source.getNode(), source.toString()
 