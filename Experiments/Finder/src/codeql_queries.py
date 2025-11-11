QL_SOURCE_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedSource(DataFlow::Node src) {{
{body}
}}

{additional}
"""

QL_SINK_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedSink(DataFlow::Node snk) {{
{body}
}}

{additional}
"""

QL_SUBSET_PREDICATE = """\
predicate isGPTDetected{kind}Part{part_id}(DataFlow::Node {node}) {{
{body}
}}
"""

CALL_QL_SUBSET_PREDICATE = "    isGPTDetected{kind}Part{part_id}({node})"

QL_STEP_PREDICATE = """\
import java
import semmle.code.java.dataflow.DataFlow
private import semmle.code.java.dataflow.ExternalFlow

predicate isGPTDetectedStep(DataFlow::Node prev, DataFlow::Node next) {{
{body}
}}
"""

QL_METHOD_CALL_SOURCE_BODY_ENTRY = """\
    (
        src.asExpr().(Call).getCallee().getName() = "{method}" and
        src.asExpr().(Call).getCallee().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}")
    )\
"""

QL_FUNC_PARAM_SOURCE_ENTRY = """\
    exists(Parameter p |
        src.asParameter() = p and
        p.getCallable().getName() = "{method}" and
        p.getCallable().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}") and
        ({params})
    )\
"""

QL_FUNC_PARAM_NAME_ENTRY = """ p.getName() = "{arg_name}" """

QL_SUMMARY_BODY_ENTRY = """\
    exists(Call c |
        (c.getArgument(_) = prev.asExpr() or c.getQualifier() = prev.asExpr())
        and c.getCallee().getDeclaringType().hasQualifiedName("{package}", "{clazz}")
        and c.getCallee().getName() = "{method}"
        and c = next.asExpr()
    )\
"""

QL_SINK_BODY_ENTRY = """\
    exists(Call c |
        c.getCallee().getName() = "{method}" and
        c.getCallee().getDeclaringType().getSourceDeclaration().hasQualifiedName("{package}", "{clazz}") and
        ({args})
    )\
"""

QL_SINK_ARG_NAME_ENTRY = """ c.getArgument({arg_id}) = snk.asExpr().(Argument) """

QL_SINK_ARG_THIS_ENTRY = """ c.getQualifier() = snk.asExpr() """

QL_BODY_OR_SEPARATOR = "\n    or\n"

EXTENSION_YML_TEMPLATE = """\
extensions:
  - addsTo:
      pack: codeql/java-all
      extensible: sinkModel
    data:
{sinks}
  - addsTo:
      pack: codeql/java-all
      extensible: sourceModel
    data:
{sources}
"""

EXTENSION_SRC_SINK_YML_ENTRY = """\
      - ["{package}", "{clazz}", True, "{method}", "", "", "{access}", "{tag}", "manual"]\
"""

EXTENSION_SUMMARY_YML_ENTRY = """\
      - ["{package}", "{clazz}", True, "{method}", "", "", "{access_in}", "{access_out}", "{tag}", "manual"]\
"""
