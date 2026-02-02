Spark - a tiny web framework for Java 8
Important - There is a vulnerability in older versions of Spark (versions lower than 2.5.2). Please upgrade to the latest version.
For documentation please go to: http://sparkjava.com/documentation
For usage questions, please use [stack overflow with the “spark-java” tag](http://stackoverflow.com/questions/tagged/spark-java)
Javadoc: http://javadoc.io/doc/com.sparkjava/spark-core
Getting started
import static spark.Spark.*;
public class HelloWorld {
public static void main(String[] args) {
get("/hello", (request, response) -> "Hello World!");
View at: http://localhost:4567/hello