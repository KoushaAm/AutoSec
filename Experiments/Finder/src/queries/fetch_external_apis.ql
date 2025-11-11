import java

predicate isExternallCall(Call c) {
    (
        not c.getCallee().getDeclaringType().getPackage().getName().matches("org.junit%") and
        not c.getCallee().getDeclaringType().getPackage().getName().matches("org.hamcrest%") and
        not c.getCallee().getDeclaringType().getPackage().getName().matches("org.mockito%") and
        not c.getCallee().getDeclaringType().getPackage().getName().matches("junit.framework%")
    )
}

bindingset[m]
string fullSignature(Callable m) {
    if m instanceof Constructor
    then
        result = m.getName() + "(" + concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName() + " " + m.getParameter(i).getName(), ", "  order by i asc)  + ")"
    else
        result = m.getReturnType().getName() + " " + m.getName() + "(" + concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName() + " " + m.getParameter(i).getName(), ", "  order by i asc)  + ")"
}

bindingset[m]
string paramTypes(Callable m) {
    result = concat(int i | i = [0 .. m.getNumberOfParameters()] | m.getParameter(i).getType().getName(), ";" order by i asc)
}


string isStaticAsString(Callable m) {
    if m.isStatic()
    then result = "true"
    else result = "false"
}

bindingset[m]
string getJavadocString(Callable m) {
    (
        exists(Javadoc d | m.getDoc().getJavadoc() = d) and
        result = concat(int i | i = [0 .. m.getDoc().getJavadoc().getNumChild()] | m.getDoc().getJavadoc().getChild(i).getText(), " " order by i asc)
    )
    or
    result = ""
}

from
    Call api
where
    isExternallCall(api) and
    api.getCallee().getStringSignature() != "()" and
    api.getCallee().getDeclaringType().getSourceDeclaration().getName() != "Object"
select
    api as callstr,
    api.getCallee().getDeclaringType().getSourceDeclaration().getPackage() as package,
    api.getCallee().getDeclaringType().getSourceDeclaration() as clazz,
    fullSignature(api.getCallee()) as full_signature,
    api.getCallee().getStringSignature() as internal_signature,
    api.getCallee() as func,
    isStaticAsString(api.getCallee()) as is_static,
    api.getFile() as file,
    api.getLocation().toString() as location,
    paramTypes(api.getCallee()) as parameter_types,
    api.getCallee().getReturnType().getName() as return_type,
    getJavadocString(api.getCallee()) as doc
