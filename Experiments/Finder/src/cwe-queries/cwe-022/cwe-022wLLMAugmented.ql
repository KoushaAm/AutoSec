/**
 * @name Uncontrolled data used in path expression
 * @description Accessing paths influenced by users can allow an attacker to access unexpected resources.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 7.5
 * @precision high
 * @id java/my-path-injection
 * @tags security
 *       external/cwe/cwe-022
 *       external/cwe/cwe-023
 *       external/cwe/cwe-036
 *       external/cwe/cwe-073
 */

 import java
 import semmle.code.java.security.PathCreation

 //from semmle.code.java.security.TaintedPathQuery
 import semmle.code.java.frameworks.Networking
 import semmle.code.java.dataflow.DataFlow
 import semmle.code.java.dataflow.FlowSources
 private import semmle.code.java.dataflow.ExternalFlow
 import semmle.code.java.security.PathSanitizer
import MySources
import MySinks

//  predicate isGPTDetectedSourceMethod(Method m) {
//    (
//      m.getName() = "getHeader" and
//      m.getDeclaringType().getAnAncestor().hasQualifiedName("javax.servlet.http", "HttpServletRequest")
//    ) or
//    (
//      m.getName() = "getPathInfo" and
//      m.getDeclaringType().getAnAncestor().hasQualifiedName("javax.servlet.http", "HttpServletRequest")
//    )
//  }

//  predicate isGPTDetectedSourceField(Field f) {
//    (
//      f.getName() = "Form" and
//      f.getDeclaringType().getAnAncestor().hasQualifiedName("javax.servlet.http", "HttpServletRequest")
//    )
//  }

//  predicate isGPTDetectedSinkMethodCall(Call c) {
//    (
//      c.getCallee().getDeclaringType().getAnAncestor().hasQualifiedName("java.net", "URL") and
//      c.getCallee().getName() = "getFile"
//    )
//  }

//  predicate isGPTDetectedSinkArgument(Argument a) {
//    (
//      a.getCall().getCallee().getDeclaringType().getAnAncestor().hasQualifiedName("java.lang", "Runtime") and
//      a.getCall().getCallee().getName() = "exec" and
//      a.getPosition() = 0
//    )
//  }

//  predicate isGPTDetectedTaintPropArgument(Argument a) {
//    (
//      a.getCall().getCallee().getDeclaringType().getAnAncestor().hasQualifiedName("java.net", "URL") and
//      a.getCall().getCallee().getName() = "URL"
//    )
//  }

/**
* A unit class for adding additional taint steps.
*
* Extend this class to add additional taint steps that should apply to tainted path flow configurations.
*/
class TaintedPathAdditionalTaintStep extends Unit {
  abstract predicate step(DataFlow::Node n1, DataFlow::Node n2);
}

private class MyTaintedPathAdditionalTaintStep extends TaintedPathAdditionalTaintStep {
  override predicate step(DataFlow::Node src, Dataflow::Node sink) {
    exists(Argument arg |
      arg = src.asExpr() and
      arg.getCall() = sink.asExpr() and
      isGPTDetectedTaintPropArgument(arg)
    )
  }
}

private class DefaultTaintedPathAdditionalTaintStep extends TaintedPathAdditionalTaintStep {
  override predicate step(DataFlow::Node n1, DataFlow::Node n2) {
    exists(Argument a |
      a = n1.asExpr() and
      a.getCall() = n2.asExpr() and
      a = any(TaintPreservingUriCtorParam tpp).getAnArgument()
    )
  }
}

private class TaintPreservingUriCtorParam extends Parameter {
  TaintPreservingUriCtorParam() {
    exists(Constructor ctor, int idx, int nParams |
      ctor.getDeclaringType() instanceof TypeUri and
      this = ctor.getParameter(idx) and
      nParams = ctor.getNumberOfParameters()
    |
      // URI(String scheme, String ssp, String fragment)
      idx = 1 and nParams = 3
      or
      // URI(String scheme, String host, String path, String fragment)
      idx = [1, 2] and nParams = 4
      or
      // URI(String scheme, String authority, String path, String query, String fragment)
      idx = 2 and nParams = 5
      or
      // URI(String scheme, String userInfo, String host, int port, String path, String query, String fragment)
      idx = 4 and nParams = 7
    )
  }
}

/**
* A taint-tracking configuration for tracking flow from remote sources to the creation of a path.
*/
module MyTaintedPathConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    // return value of method call
    isGPTDetectedSourceMethod(source.asExpr().(MethodCall).getMethod()) or
    source instanceof ThreatModelFlowSource

    // field read
    //isGPTDetectedSourceField(source.asExpr().(FieldAccess).getField())
  }

  predicate isSink(DataFlow::Node sink) {
    // callee of a method call
    //isGPTDetectedSinkMethodCall(sink.asExpr().(Call)) or

    // an argument to a method call
    isGPTDetectedSinkArgument(sink.asExpr().(Argument)) or
    sinkNode(sink, "path-injection")
  }

  predicate isBarrier(DataFlow::Node sanitizer) {
    sanitizer.getType() instanceof BoxedType or
    sanitizer.getType() instanceof PrimitiveType or
    sanitizer.getType() instanceof NumberType or
    sanitizer instanceof PathInjectionSanitizer
  }

  predicate isAdditionalFlowStep(DataFlow::Node n1, DataFlow::Node n2) {
    any(TaintedPathAdditionalTaintStep s).step(n1, n2)
  }
}

/** Tracks flow from remote sources to the creation of a path. */
module MyTaintedPathFlow = TaintTracking::Global<MyTaintedPathConfig>;


/**
* Gets the data-flow node at which to report a path ending at `sink`.
*
* Previously this query flagged alerts exclusively at `PathCreation` sites,
* so to avoid perturbing existing alerts, where a `PathCreation` exists we
* continue to report there; otherwise we report directly at `sink`.
*/
DataFlow::Node getReportingNode(DataFlow::Node sink) {
  MyTaintedPathFlow::flowTo(sink) and
  if exists(PathCreation pc | pc.getAnInput() = sink.asExpr())
  then result.asExpr() = any(PathCreation pc | pc.getAnInput() = sink.asExpr())
  else result = sink
}

from MyTaintedPathFlow::PathNode source, MyTaintedPathFlow::PathNode sink
where MyTaintedPathFlow::flowPath(source, sink)
select getReportingNode(sink.getNode()), source, sink, "This path depends on a $@.",
  source.getNode(), "user-provided value"
