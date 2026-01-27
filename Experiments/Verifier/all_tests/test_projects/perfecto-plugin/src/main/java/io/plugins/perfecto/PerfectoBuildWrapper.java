package io.plugins.perfecto;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.Serializable;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.annotation.Nonnull;

import org.jenkins_ci.plugins.run_condition.RunCondition;
import org.jenkinsci.Symbol;
import org.kohsuke.stapler.AncestorInPath;
import org.kohsuke.stapler.DataBoundConstructor;
import org.kohsuke.stapler.QueryParameter;
import org.kohsuke.stapler.verb.POST;

import com.cloudbees.plugins.credentials.CredentialsMatchers;
import com.cloudbees.plugins.credentials.CredentialsProvider;
import com.cloudbees.plugins.credentials.common.StandardUsernameListBoxModel;
import com.google.common.base.Strings;

import edu.umd.cs.findbugs.annotations.SuppressFBWarnings;
import hudson.AbortException;
import hudson.Extension;
import hudson.FilePath;
import hudson.Launcher;
import hudson.Proc;
import hudson.Util;
import hudson.model.AbstractBuild;
import hudson.model.AbstractProject;
import hudson.model.BuildListener;
import hudson.model.BuildableItemWithBuildWrappers;
import hudson.model.Computer;
import hudson.model.Item;
import hudson.model.ItemGroup;
import hudson.model.listeners.ItemListener;
import hudson.security.ACL;
import hudson.security.AccessControlled;
import hudson.tasks.BatchFile;
import hudson.tasks.BuildWrapper;
import hudson.tasks.BuildWrapperDescriptor;
import hudson.tasks.CommandInterpreter;
import hudson.tasks.Shell;
import hudson.util.FormValidation;
import hudson.util.ListBoxModel;
import io.plugins.perfecto.credentials.PerfectoCredentials;
import jenkins.model.Jenkins;

/**
 * {@link BuildWrapper} that sets up the Perfecto connect tunnel and populates environment variable.
 *
 * @author Dushyantan Satike, Genesis
 */
public class PerfectoBuildWrapper extends BuildWrapper implements Serializable {

	/**
	 * Logger instance.
	 */
	private static final Logger logger = Logger.getLogger(PerfectoBuildWrapper.class.getName());
	private static final long serialVersionUID = 6106269076155338045L;
	/**
	 * Environment variable key which contains the Perfecto Security token.
	 */
	public static final String PERFECTO_SECURITY_TOKEN = "perfectoSecurityToken";
	/**
	 * Environment variable key which contains the Perfecto Cloud name.
	 */
	public static final String PERFECTO_CLOUD_NAME = "perfectoCloudName";

	public static final Pattern ENVIRONMENT_VARIABLE_PATTERN = Pattern.compile("[$|%][{]?([a-zA-Z_][a-zA-Z0-9_]+)[}]?");
	private transient Computer computer;
	/**
	 * The custom Tunnel Id name.
	 */
	private String tunnelIdCustomName = "tunnelId";
	/**
	 * Indicates whether Perfecto Connect should be started as part of the build.
	 */
	private boolean enablePerfectoConnect;
	/**
	 * The path of the Perfecto connect location.
	 */
	private String perfectoConnectLocation;
	/**
	 * The path of the Perfecto security token.
	 */
	private String perfectoSecurityToken;

	/**
	 * The Perfecto Connect parameters.
	 */
	private String pcParameters = " ";

	private String reuseTunnelId = " ";

	private PerfectoCredentials credentials;

	@SuppressFBWarnings("SE_BAD_FIELD")
	private RunCondition condition;
	/**
	 * @see CredentialsProvider
	 */
	private String credentialId;

	private String tunnelId = null;

	private String perfectoConnectFile = "";

	private String pcLocation = "";

	private String regex = "^[^>|;\\{}()\\&&<^]*$";

	 private transient Launcher launcher;
	 
	@Override
	public void makeSensitiveBuildVariables(AbstractBuild build, Set<String> sensitiveVariables) {
		super.makeSensitiveBuildVariables(build, sensitiveVariables);
		sensitiveVariables.add(PERFECTO_SECURITY_TOKEN);
	}

	/**
	 * Constructs a new instance using data entered on the job configuration screen.
	 * @param condition                 allows users to define rules which enable Perfecto Connect
	 * @param credentialId              Which credential a build should use
	 * @param tunnelIdCustomName        Custom value for tunnel Id environment variable name.
	 * @param pcParameters              Perfecto Connect parameters
	 * @param perfectoConnectLocation   Perfecto connect location
	 * @param perfectoSecurityToken     Perfecto Security token.
	 * @param perfectoConnectFile       Perfecto connect file name.
	 * @param reuseTunnelId				Tunnel ID to reuse.
	 */
	@DataBoundConstructor
	public PerfectoBuildWrapper(
			RunCondition condition,
			String credentialId,
			String tunnelIdCustomName,
			String pcParameters,
			String perfectoConnectLocation,
			String perfectoSecurityToken,
			String perfectoConnectFile,
			String reuseTunnelId
			) {
		this.launcher = null;
		System.out.println(perfectoConnectLocation);
		if(perfectoConnectLocation.trim().matches(regex)) {
			this.perfectoConnectLocation = perfectoConnectLocation;
		}else {
			throw new IllegalArgumentException("Perfecto location doesnt seem to be valid.");
		}
		this.condition = condition;
		if(tunnelIdCustomName.length()>1)
			if(tunnelIdCustomName.trim().matches(regex)) {
				this.tunnelIdCustomName = tunnelIdCustomName;
			}else {
				throw new IllegalArgumentException("Custom tunnel id doesnt seem to be valid.");
			}

		this.credentialId = credentialId;
		this.perfectoSecurityToken = perfectoSecurityToken;
		if (Util.fixEmptyAndTrim(pcParameters) != null) {
			if(pcParameters.trim().matches(regex)) {
				this.pcParameters = pcParameters;
			}else {
				throw new IllegalArgumentException("Additional parameters doesnt seem to be valid.");
			}
		}else {
			this.pcParameters = " ";
		}
		if(perfectoConnectFile.trim().matches(regex)) {
			this.perfectoConnectFile = perfectoConnectFile;
		}else {
			throw new IllegalArgumentException("perfectoConnectFile doesnt seem to be valid.");
		}
		if (Util.fixEmptyAndTrim(reuseTunnelId) != null) {
			if(reuseTunnelId.trim().matches(regex)) {
				this.reuseTunnelId = reuseTunnelId;
			}else {
				throw new IllegalArgumentException("Existing tunnel id doesnt seem to be valid.");
			}
		}else {
			this.reuseTunnelId = " ";
		}

	}

	private @Nonnull Computer getComputer() throws AbortException {
        if (computer != null) {
            return computer;
        }

        String node = null;
        Jenkins j = Jenkins.getActiveInstance();

        for (Computer c : j.getComputers()) {
            if (c.getChannel() == launcher.getChannel()) {
                node = c.getName();
                break;
            }
        }

        if (node == null) {
            throw new AbortException("Could not find computer for the job");
        }

        computer = j.getComputer(node);
        if (computer == null) {
            throw new AbortException("No such computer " + node);
        }

        if (logger.isLoggable(Level.FINE)) {
        	logger.log(Level.FINE, "Computer: {0}", computer.getName());
            try {
            	logger.log(Level.FINE, "Env: {0}", computer.getEnvironment());
            } catch (IOException | InterruptedException e) {// ignored
            }
        }
        return computer;
    }
	
	/**
	 * {@inheritDoc}
	 *
	 * Invoked prior to the running of a Jenkins build.  Populates the Perfecto specific environment variables and launches Perfecto Connect.
	 *
	 * @return a new {@link hudson.model.Environment} instance populated with the Perfecto environment variables
	 */
	@Override
	public Environment setUp(final AbstractBuild build, Launcher launcher, final BuildListener listener) throws IOException, InterruptedException {
		this.launcher = launcher;
		listener.getLogger().println("Creating Tunnel Id........!");
		logger.fine("Setting Perfecto Build Wrapper");

		credentials = PerfectoCredentials.getPerfectoCredentials(build, this);
		CredentialsProvider.track(build, credentials);

		if(credentials==null && !reuseTunnelId.trim().contains("-")) {
			listener.fatalError("Credentials missing...... ");
			throw new IOException("Credentials missing......One reason to see this error is to check if you had selected the required credentials in build environment section.");
		}
		if(!reuseTunnelId.trim().contains("-")) {
			final String apiKey = credentials.getPassword().getPlainText();
			if(perfectoConnectLocation.endsWith("/")||perfectoConnectLocation.endsWith("\\")) {
				pcLocation = perfectoConnectLocation+perfectoConnectFile;
			}else {
				pcLocation = perfectoConnectLocation+File.separator+perfectoConnectFile;
			}
			String baseCommand = pcLocation.trim()+" start -c "+credentials.getCloudName().trim()+".perfectomobile.com -s " + apiKey.trim();
			listener.getLogger().println(pcLocation.trim()+" start -c "+credentials.getCloudName().trim()+".perfectomobile.com -s <<TOKEN>> "+pcParameters.trim());
			String script = baseCommand+" "+pcParameters.trim();

			List<String> reader = new ArrayList<String>();
			try {
					ByteArrayOutputStream baos = new ByteArrayOutputStream();
					Proc p  = launcher.launch(launcher.new ProcStarter().pwd(new FilePath(new File(perfectoConnectLocation))).cmds(script.split(" ")).stdout(baos));
					for (int i = 0; p.isAlive() && i < 200; i++) {
						Thread.sleep(100);
					}
					int exitCode = p.join();
					if (exitCode == 0) {
						reader.add(baos.toString(getComputer().getDefaultCharset().name()).replaceAll("[\t\r\n]+", " ").trim());
					} else {
						return null;
					}
			} catch (IOException e) {
				listener.fatalError("Unable to create tunnel ID. Kindly cross check your parameters or raise a Perfecto support case."+e.getMessage());
				throw new IOException("Unable to create tunnel ID. Kindly cross check your parameters or raise a Perfecto support case."+e.getMessage());
			}
			String s = null;
			for(int i = 0; i < reader.size(); i++) {
				s = reader.get(i).toString();
				//				listener.getLogger().println(s); // Debug
				Matcher m = Pattern.compile("^[A-Za-z0-9-]+$").matcher(s);
				if (m.find()) {
					tunnelId = m.group(0);
					listener.getLogger().println("Tunnel Id : "+tunnelId);
					break;
				}
				if(s.contains("bash: ")) {
					listener.fatalError("Perfecto Connect Path and Name is not Correct. Path Provided : '"+pcLocation+"'");
					throw new IOException("Perfecto Connect Path and Name is not Correct. Path Provided : '"+pcLocation+"'");
				}
				if(s.contains("Can't start Perfecto Connect")||s.contains("failed to start")) {
					listener.fatalError(tunnelId);
					throw new IOException(tunnelId);
				}
			}
			if(tunnelId == null) {
				listener.fatalError("Unable to create tunnel ID. Kindly cross check your parameters or raise a Perfecto support case.");
				throw new IOException("Unable to create tunnel ID. Kindly cross check your parameters or raise a Perfecto support case.");
			}
			listener.getLogger().println("Tunnel Id created succesfully.");
		}else {
			tunnelId = reuseTunnelId;
		}

		return new Environment() {

			/**
			 * Updates the environment variable map to include the Perfecto specific environment variables applicable to the build.
			 * @param env existing environment variables
			 */
			@Override
			public void buildEnvVars(Map<String, String> env) {
				listener.getLogger().println("Setting Perfecto tunnel id to Environment variable: "+tunnelIdCustomName);
				PerfectoEnvironmentUtil.outputEnvironmentVariable(env, tunnelIdCustomName, tunnelId, true);
			}
			/**
			 * {@inheritDoc}
			 *
			 * Tear down method
			 * @param build
			 *      The build in progress for which an {@link Environment} object is created.
			 *      Never null.
			 * @param listener
			 *      Can be used to send any message.
			 *
			 */
			@Override
			public boolean tearDown(AbstractBuild build, BuildListener listener) throws IOException, InterruptedException {
				return true;
			}
		};
	}

	/**
	 * This method will return the command intercepter as per the node OS
	 * 
	 * @param launcher
	 * @param script
	 * @return CommandInterpreter
	 */
	private CommandInterpreter getCommandInterpreter(Launcher launcher,
			String script) {
		if (launcher.isUnix())
			return new Shell(script);
		else
			return new BatchFile(script);
	}

	public boolean isEnablePerfectoConnect() {
		return enablePerfectoConnect;
	}

	public void setEnablePerfectoConnect(boolean enablePerfectoConnect) {
		this.enablePerfectoConnect = enablePerfectoConnect;
	}

	public String getTunnelIdCustomName() {
		return tunnelIdCustomName;
	}

	public void setTunnelIdCustomName(String tunnelIdCustomName) {
		this.tunnelIdCustomName = tunnelIdCustomName;
	}

	public String getPerfectoConnectFile() {
		return perfectoConnectFile;
	}

	public void setPerfectoConnectFile(String perfectoConnectFile) {
		this.perfectoConnectFile = perfectoConnectFile;
	}

	public String getPerfectoConnectLocation() {
		return perfectoConnectLocation;
	}

	public void setPerfectoConnectLocation(String perfectoConnectLocation) {
		this.perfectoConnectLocation = perfectoConnectLocation;
	}

	public String getSecurityToken() {
		return perfectoSecurityToken;
	}

	public void setSecurityToken(String perfectoSecurityToken) {
		this.perfectoSecurityToken = perfectoSecurityToken;
	}

	public RunCondition getCondition() {
		return condition;
	}

	public String getCredentialId() {
		return credentialId;
	}

	public void setCredentialId(String credentialId) {
		this.credentialId = credentialId;
	}

	public String getPcParameters() {
		return pcParameters;
	}

	public void setPcParameters(String pcParameters) {
		this.pcParameters = pcParameters;
	}

	@Extension(ordinal = 1.0D)
	@Symbol("withPerfecto")
	public static class DescriptorImpl extends BuildWrapperDescriptor {
		/**
		 * @return text to be displayed within Jenkins job configuration
		 */
		@Override
		public String getDisplayName() {
			return "Perfecto Connect";
		}

		/**
		 *Fills credentials
		 *
		 * @param context  ItemGroup
		 * @param credentialId credentials
		 * @return the list of supported credentials
		 */
		@POST
		public ListBoxModel doFillCredentialIdItems(final @AncestorInPath ItemGroup<?> context, @QueryParameter String credentialId) {
			Jenkins.get().checkPermission(Jenkins.ADMINISTER);
			Jenkins jenkins = Jenkins.getInstanceOrNull();
			if (jenkins == null)
				return null;

			if (context == null || !jenkins.hasPermission(Jenkins.ADMINISTER))
				return new StandardUsernameListBoxModel().includeCurrentValue(credentialId);

			if (!((AccessControlled) context).hasPermission(Item.CONFIGURE)) {
				return new StandardUsernameListBoxModel();
			}

			return new StandardUsernameListBoxModel()
					.includeAs(ACL.SYSTEM, context, PerfectoCredentials.class)
					.includeCurrentValue(credentialId);
		}

		/**
		 * Validates Credential if exists
		 *
		 * @param item  Basic configuration unit in Hudson
		 * @param value Any conditional parameter(here id of the credential selected)
		 * @return FormValidation
		 */
		@POST
		public FormValidation doCheckCredentialId(@AncestorInPath Item item, @QueryParameter String value) {
			Jenkins.get().checkPermission(Jenkins.ADMINISTER); 
			if (item != null && !value.trim().isEmpty()) {
				return FormValidation.ok();
			}

			if (value == null || value.isEmpty()|| CredentialsProvider.listCredentials(PerfectoCredentials.class, item, ACL.SYSTEM, Collections.emptyList(), CredentialsMatchers.withId(value)).isEmpty()) {
				return FormValidation.error("Add/ Select a Perfecto kind credentials with valid Cloud Name, Username and Security Token.");
			}
			return FormValidation.ok();
		}

		@POST
		public FormValidation doCheckPerfectoConnectLocation(@QueryParameter String value, @AncestorInPath Item item) {
			if (item == null) { 
				return FormValidation.ok();
			}
			item.checkPermission(Item.CONFIGURE);

			if (Util.fixEmptyAndTrim(value) == null) {
				return FormValidation.error("Perfecto connect location cannot be empty");
			}
			return FormValidation.ok();
		}

		@POST
		public FormValidation doCheckPerfectoConnectFile(@QueryParameter String value, @AncestorInPath Item item) {
			if (item == null) { 
				return FormValidation.ok();
			}
			item.checkPermission(Item.CONFIGURE);

			if (Util.fixEmptyAndTrim(value) == null) {
				return FormValidation.error("Perfecto connect file name cannot be empty");
			}
			return FormValidation.ok();
		}

		@Override
		public boolean isApplicable(AbstractProject<?, ?> item) {
			// TODO Auto-generated method stub
			return true;
		}

	}

	protected boolean migrateCredentials(AbstractProject project) {
		if (Strings.isNullOrEmpty(credentialId)) {
			if (credentials != null) {
				try {
					credentialId = PerfectoCredentials.migrateToCredentials(
							credentials.getUsername(),
							credentials.getCloudName(),
							credentials.getApiKey().getPlainText(),
							project == null ? "Unknown" : project.getDisplayName()
							);
					return true;
				} catch (InterruptedException e) {
					e.printStackTrace();
				} catch (IOException e) {
					e.printStackTrace();
				}
			}
			try {
				if (credentials != null) {
					this.credentialId = PerfectoCredentials.migrateToCredentials(
							credentials.getUsername(),
							credentials.getCloudName(),
							credentials.getApiKey().getPlainText(),
							"Global"
							);
					return true;
				}
			} catch (InterruptedException e) {
				e.printStackTrace();
			} catch (IOException e) {
				e.printStackTrace();
			}
		}
		return false;
	}

	@Extension
	static final public class ItemListenerImpl extends ItemListener {
		public void onLoaded() {
			Jenkins instance = Jenkins.getInstance();
			if (instance == null) { return; }
			for (BuildableItemWithBuildWrappers item : instance.getItems(BuildableItemWithBuildWrappers.class))
			{
				AbstractProject p = item.asProject();
				for (PerfectoBuildWrapper bw : ((BuildableItemWithBuildWrappers)p).getBuildWrappersList().getAll(PerfectoBuildWrapper.class))
				{
					if (bw.migrateCredentials(p)) {
						try {
							p.save();
						} catch (IOException e) {
							e.printStackTrace();
						}
					}
				}
			}
		}
	}
}