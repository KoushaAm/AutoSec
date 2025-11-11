/** Provides taint tracking configurations to be used in Trust Manager queries. */

import java
import semmle.code.java.dataflow.FlowSources
import MyInsecureTrustManager
import MySources
import MySinks

/**
 * A configuration to model the flow of an insecure `TrustManager`
 * to the initialization of an SSL context.
 */
module MyInsecureTrustManagerConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) { 
    //source instanceof InsecureTrustManagerSource 
    isGPTDetectedSourceMethod(source.asExpr().(MethodCall).getMethod())
}

  predicate isSink(DataFlow::Node sink) { 
    //sink instanceof InsecureTrustManagerSink 
    (isGPTDetectedSinkMethodCall(sink.asExpr().(Call)) or
    isGPTDetectedSinkArgument(sink.asExpr().(Argument)) )
    and not isGuardedByInsecureFlag(this)
}

  predicate allowImplicitRead(DataFlow::Node node, DataFlow::ContentSet c) {
    (isSink(node) or isAdditionalFlowStep(node, _)) and
    node.getType() instanceof Array and
    c instanceof DataFlow::ArrayContent
  }
}

module MyInsecureTrustManagerFlow = DataFlow::Global<MyInsecureTrustManagerConfig>;
