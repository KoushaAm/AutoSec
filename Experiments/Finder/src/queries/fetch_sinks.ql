import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

import MySinks

from
  DataFlow::Node node
where
  isGPTDetectedSink(node)
select
  node.toString() as node_str,
  node.getLocation() as loc
