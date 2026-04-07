import java

bindingset[m]
string fullSignature(Callable m) {
    if m instanceof Constructor
    then
        result = m.getName() + "(" + concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName() + " " + m.getParameter(i).getName(), ", "  order by i asc)  + ")"
    else
        result = m.getReturnType().getName() + " " + m.getName() + "(" + concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName() + " " + m.getParameter(i).getName(), ", "  order by i asc)  + ")"
}

predicate isTested(Callable m) {
    exists(Call c |
        c.getCallee() = m and
        c.getLocation().toString().indexOf("src/test") >= 0
    )
}

predicate isNotInvokedByInternalFunction(Callable m) {
    not exists(Call c |
        c.getCallee() = m and
        c.getLocation().toString().indexOf("src/test") < 0
    )
}

bindingset[m]
string paramTypes(Callable m) {
    result = concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName(), ";" order by i asc)
}

bindingset[m]
string getJavadocString(Callable m) {
    if (exists(Javadoc d | m.getDoc().getJavadoc() = d))
    then
        result = concat(int i | i = [0 .. m.getDoc().getJavadoc().getNumChild()] | m.getDoc().getJavadoc().getChild(i).getText(), " " order by i asc)
    else
        result = ""
}

from
    Callable method
where
    method.fromSource() and
    method.isPublic() and
    not method.hasNoParameters() and
    isTested(method) and
    isNotInvokedByInternalFunction(method)
select
    method.getDeclaringType().getSourceDeclaration().getPackage() as package,
    method.getDeclaringType().getSourceDeclaration() as clazz,
    method.getName() as func,
    fullSignature(method) as full_signature,
    method.getStringSignature() as internal_signature,
    method.getLocation().toString() as location,
    paramTypes(method) as parameter_types,
    method.getReturnType().getName() as return_type,
    getJavadocString(method) as doc
