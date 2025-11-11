/** Provides a taint-tracking configuration to reason about cross-site scripting from a local source. */

import java
private import semmle.code.java.dataflow.FlowSources
private import semmle.code.java.dataflow.TaintTracking
private import MyXSS

import MySources
import MySinks
import MySummaries

/**
 * A taint-tracking configuration for reasoning about cross-site scripting vulnerabilities from a local source.
 */
module MyXssLocalConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    source instanceof LocalUserInput
  }

  predicate isSink(DataFlow::Node sink) {
    isGPTDetectedSink(sink)
  }

  predicate isBarrier(DataFlow::Node node) { node instanceof XssSanitizer }

  predicate isBarrierOut(DataFlow::Node node) { node instanceof XssSinkBarrier }

  predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
    any(XssAdditionalTaintStep s).step(node1, node2) or
    isGPTDetectedStep(node1, node2)
  }
}

/**
 * Taint-tracking flow for cross-site scripting vulnerabilities from a local source.
 */
module MyXssLocalFlow = TaintTracking::Global<MyXssLocalConfig>;
