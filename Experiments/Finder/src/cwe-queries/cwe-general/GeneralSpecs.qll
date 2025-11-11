/** Provides dataflow configurations for tainted path queries. */

import java
import semmle.code.java.frameworks.Networking
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.FlowSources
private import semmle.code.java.dataflow.ExternalFlow

import MySources
import MySinks


/**
 * A taint-tracking configuration for tracking flow from remote sources to the creation of a path.
 */
module MyPathConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { 
    isGPTDetectedSourceMethod(source.asExpr().(MethodCall).getMethod()) 
 }

  predicate isSink(DataFlow::Node sink) { 
    isGPTDetectedSinkMethodCall(sink.asExpr().(Call)) or
 
    // an argument to a method call
    isGPTDetectedSinkArgument(sink.asExpr().(Argument))
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

