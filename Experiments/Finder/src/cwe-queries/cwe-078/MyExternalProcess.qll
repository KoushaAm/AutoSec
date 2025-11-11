/** Definitions related to external processes. */

import semmle.code.java.Member
private import semmle.code.java.dataflow.DataFlow
private import MyCommandLineQuery

/**
 * DEPRECATED: A callable that executes a command.
 */
abstract deprecated class MyExecCallable extends Callable {
  /**
   * Gets the index of an argument that will be part of the command that is executed.
   */
  abstract int getAnExecutedArgument();
}

/**
 * An expression used as an argument to a call that executes an external command. For calls to
 * varargs method calls, this only includes the first argument, which will be the command
 * to be executed.
 */
class MyArgumentToExec extends Expr {
  MyArgumentToExec() { myargumentToExec(this, _) }
}

/**
 * Holds if `e` is an expression used as an argument to a call that executes an external command.
 * For calls to varargs method calls, this only includes the first argument, which will be the command
 * to be executed.
 */
predicate myargumentToExec(Expr e, CommandInjectionSink s) {
  s.asExpr() = e
  or
  e.(Argument).isNthVararg(0) and
  s.(DataFlow::ImplicitVarargsArray).getCall() = e.(Argument).getCall()
}

/**
 * An `ArgumentToExec` of type `String`.
 */
class MyStringArgumentToExec extends MyArgumentToExec {
  MyStringArgumentToExec() { this.getType() instanceof TypeString }
}
