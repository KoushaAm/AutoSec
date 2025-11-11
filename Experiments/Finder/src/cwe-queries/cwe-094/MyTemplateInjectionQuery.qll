/** Provides a taint tracking configuration for server-side template injection (SST) vulnerabilities */

import java
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import MyTemplateInjection
import MySources
import MySinks

/** A taint tracking configuration to reason about server-side template injection (SST) vulnerabilities */
module MyTemplateInjectionFlowConfig implements DataFlow::StateConfigSig {
  class FlowState = DataFlow::FlowState;

  predicate isSource(DataFlow::Node source, FlowState state) {
    source.(TemplateInjectionSource).hasState(state)
  }

  predicate isSink(DataFlow::Node sink, FlowState state) {
    sink.(TemplateInjectionSink).hasState(state)
  }

  predicate isBarrier(DataFlow::Node sanitizer) { sanitizer instanceof TemplateInjectionSanitizer }

  predicate isBarrier(DataFlow::Node sanitizer, FlowState state) {
    sanitizer.(TemplateInjectionSanitizerWithState).hasState(state)
  }

  predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
    any(TemplateInjectionAdditionalTaintStep a).isAdditionalTaintStep(node1, node2)
  }

  predicate isAdditionalFlowStep(
    DataFlow::Node node1, FlowState state1, DataFlow::Node node2, FlowState state2
  ) {
    any(TemplateInjectionAdditionalTaintStep a).isAdditionalTaintStep(node1, state1, node2, state2)
  }
}

/** Tracks server-side template injection (SST) vulnerabilities */
module MyTemplateInjectionFlow = TaintTracking::GlobalWithState<MyTemplateInjectionFlowConfig>;
