import java

predicate isExternalClass(Class c){
        //not c.getPackage().fromSource() and // eliminates internal packages 
        not c.getPackage().getName().matches("org.junit%") and 
        not c.getPackage().getName().matches("org.hamcrest%") and 
        not c.getPackage().getName().matches("junit.framework%")        
}


from FieldRead fr, Field f
where isExternalClass(f.getDeclaringType()) and fr.getField() = f and fr.getCompilationUnit().getPackage().fromSource()
select fr as fieldread, 
f as field, 
f.getDeclaringType() as clazz,
f.getDeclaringType().getPackage() as package,
fr.getFile() as file, 
fr.getLocation().toString() as location

