/**
 * Provides classes and methods common to queries `java/command-line-injection`, `java/command-line-concatenation`
 * and their experimental derivatives.
 *
 * Do not import this from a library file, in order to reduce the risk of
 * unintentionally bringing a TaintTracking::Configuration into scope in an unrelated
 * query.
 */

import java
private import semmle.code.java.dataflow.FlowSources
private import semmle.code.java.dataflow.ExternalFlow
private import MyCommandArguments
private import MyExternalProcess
import MySources
import MySinks

/** A sink for command injection vulnerabilities. */
abstract class CommandInjectionSink extends DataFlow::Node { }

/** A sanitizer for command injection vulnerabilities. */
abstract class CommandInjectionSanitizer extends DataFlow::Node { }

/**
 * A unit class for adding additional taint steps.
 *
 * Extend this class to add additional taint steps that should apply to configurations related to command injection.
 */
class CommandInjectionAdditionalTaintStep extends Unit {
  /**
   * Holds if the step from `node1` to `node2` should be considered a taint
   * step for configurations related to command injection.
   */
  abstract predicate step(DataFlow::Node node1, DataFlow::Node node2);
}

private class DefaultCommandInjectionSink extends CommandInjectionSink {
  DefaultCommandInjectionSink() { sinkNode(this, "command-injection") }
}

private class DefaultCommandInjectionSanitizer extends CommandInjectionSanitizer {
  DefaultCommandInjectionSanitizer() {
    this.getType() instanceof PrimitiveType
    or
    this.getType() instanceof BoxedType
    or
    this.getType() instanceof NumberType
    or
    isSafeCommandArgument(this.asExpr())
  }
}

/**
 * A taint-tracking configuration for unvalidated user input that is used to run an external process.
 */
module MyRemoteUserInputToArgumentToExecFlowConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node src) { 
    isGPTDetectedSourceMethod(src.asExpr().(MethodCall).getMethod()) 
    // src instanceof ThreatModelFlowSource 
  }

  predicate isSink(DataFlow::Node sink) { 
    isGPTDetectedSinkMethodCall(sink.asExpr().(Call)) or
 
    // an argument to a method call
    isGPTDetectedSinkArgument(sink.asExpr().(Argument))
    //sink instanceof CommandInjectionSink 
  }

  predicate isBarrier(DataFlow::Node node) { node instanceof CommandInjectionSanitizer }

  predicate isAdditionalFlowStep(DataFlow::Node n1, DataFlow::Node n2) {
    any(CommandInjectionAdditionalTaintStep s).step(n1, n2)
  }
}

/**
 * Taint-tracking flow for unvalidated user input that is used to run an external process.
 */
module MyRemoteUserInputToArgumentToExecFlow =
  TaintTracking::Global<MyRemoteUserInputToArgumentToExecFlowConfig>;

/**
 * A taint-tracking configuration for unvalidated local user input that is used to run an external process.
 */
module MyLocalUserInputToArgumentToExecFlowConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node src) { 
    isGPTDetectedSourceMethod(src.asExpr().(MethodCall).getMethod())
    //src instanceof LocalUserInput 
  }

  predicate isSink(DataFlow::Node sink) { 
    isGPTDetectedSinkMethodCall(sink.asExpr().(Call)) or
    // an argument to a method call
    isGPTDetectedSinkArgument(sink.asExpr().(Argument))
    //sink instanceof CommandInjectionSink 
  }

  predicate isBarrier(DataFlow::Node node) { node instanceof CommandInjectionSanitizer }

  predicate isAdditionalFlowStep(DataFlow::Node n1, DataFlow::Node n2) {
    any(CommandInjectionAdditionalTaintStep s).step(n1, n2)
  }
}

/**
 * Taint-tracking flow for unvalidated local user input that is used to run an external process.
 */
module MyLocalUserInputToArgumentToExecFlow =
  TaintTracking::Global<MyLocalUserInputToArgumentToExecFlowConfig>;

/**
 * Implementation of `ExecTainted.ql`. It is extracted to a QLL
 * so that it can be excluded from `ExecUnescaped.ql` to avoid
 * reporting overlapping results.
 */
predicate execIsTainted(
  MyRemoteUserInputToArgumentToExecFlow::PathNode source,
  MyRemoteUserInputToArgumentToExecFlow::PathNode sink, Expr execArg
) {
  MyRemoteUserInputToArgumentToExecFlow::flowPath(source, sink) and
  myargumentToExec(execArg, sink.getNode())
}

/**
 * DEPRECATED: Use `execIsTainted` instead.
 *
 * Implementation of `ExecTainted.ql`. It is extracted to a QLL
 * so that it can be excluded from `ExecUnescaped.ql` to avoid
 * reporting overlapping results.
 */
deprecated predicate execTainted(DataFlow::PathNode source, DataFlow::PathNode sink, Expr execArg) {
  exists(MyRemoteUserInputToArgumentToExecFlowConfig conf |
    conf.hasFlowPath(source, sink) and myargumentToExec(execArg, sink.getNode())
  )
}

/**
 * DEPRECATED: Use `RemoteUserInputToArgumentToExecFlow` instead.
 *
 * A taint-tracking configuration for unvalidated user input that is used to run an external process.
 */
deprecated class MyRemoteUserInputToArgumentToExecFlowConfig extends TaintTracking::Configuration {
  MyRemoteUserInputToArgumentToExecFlowConfig() {
    this = "ExecCommon::RemoteUserInputToArgumentToExecFlowConfig"
  }

  override predicate isSource(DataFlow::Node src) { src instanceof RemoteFlowSource }

  override predicate isSink(DataFlow::Node sink) { sink instanceof CommandInjectionSink }

  override predicate isSanitizer(DataFlow::Node node) { node instanceof CommandInjectionSanitizer }

  override predicate isAdditionalTaintStep(DataFlow::Node n1, DataFlow::Node n2) {
    any(CommandInjectionAdditionalTaintStep s).step(n1, n2)
  }
}
