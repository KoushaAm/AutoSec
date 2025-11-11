import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

import MySources

from
  DataFlow::Node node
where
  isGPTDetectedSource(node)
select
  node.toString() as node_str,
  node.getLocation() as loc
