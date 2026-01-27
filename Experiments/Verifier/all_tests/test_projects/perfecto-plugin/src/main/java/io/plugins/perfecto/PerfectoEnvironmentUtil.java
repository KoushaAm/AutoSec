package io.plugins.perfecto;

import hudson.model.AbstractProject;
import hudson.model.BuildableItemWithBuildWrappers;

import java.util.Map;
import java.util.logging.Logger;

/**
 * Contains helper methods.
 *
 * @author Dushyantan Satike
 */
public final class PerfectoEnvironmentUtil {

	/**
	 * Logger instance.
	 */
	private static final Logger logger = Logger.getLogger(PerfectoEnvironmentUtil.class.getName());
	//
	//    //only allow word, digit, and hyphen characters
	//    private static final String PATTERN_DISALLOWED_CHARS = "[^\\w\\d-]+";

	/**
	 * Disallow instantiation of class.
	 */
	private PerfectoEnvironmentUtil() {
	}

	/**
	 * Adds the key/value pair to the map of environment variables.
	 *
	 * @param env       the map of environment variables
	 * @param key       environment variable key
	 * @param value     environment variable value
	 * @param overwrite indicates whether existing environment variables should be overwritten
	 */
	public static void outputEnvironmentVariable(Map<String, String> env, String key, String value, boolean overwrite) {
		if (env.get(key) == null || overwrite) {
			env.put(key, value);
		}
	}

	/**
	 * @param project the Jenkins project to check
	 * @return the PerfectoBuildWrapper instance associated with the project, can be null
	 */
	public static PerfectoBuildWrapper getBuildWrapper(AbstractProject<?, ?> project) {
		PerfectoBuildWrapper buildWrapper = null;
		if (project instanceof BuildableItemWithBuildWrappers) {
			buildWrapper = ((BuildableItemWithBuildWrappers) project).getBuildWrappersList().get(PerfectoBuildWrapper.class);
		} else {
			logger.fine("Project is not a BuildableItemWithBuildWrappers instance " + project.toString());
		}
		if (buildWrapper == null) {
			logger.fine("Could not find PerfectoBuildWrapper on project " + project.toString());
		}
		return buildWrapper;
	}

}
