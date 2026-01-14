package io.plugins.perfecto.credentials;

import java.io.IOException;
import java.io.Serializable;
import java.net.URL;
import java.util.Collections;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import javax.annotation.CheckForNull;
import javax.net.ssl.HttpsURLConnection;

import org.apache.commons.lang.StringUtils;
import org.kohsuke.stapler.DataBoundConstructor;
import org.kohsuke.stapler.DataBoundSetter;
import org.kohsuke.stapler.QueryParameter;
import org.kohsuke.stapler.verb.POST;

import com.auth0.jwt.JWT;
import com.auth0.jwt.exceptions.JWTCreationException;
import com.cloudbees.plugins.credentials.Credentials;
import com.cloudbees.plugins.credentials.CredentialsDescriptor;
import com.cloudbees.plugins.credentials.CredentialsMatchers;
import com.cloudbees.plugins.credentials.CredentialsProvider;
import com.cloudbees.plugins.credentials.CredentialsScope;
import com.cloudbees.plugins.credentials.SystemCredentialsProvider;
import com.cloudbees.plugins.credentials.common.StandardUsernameCredentials;
import com.cloudbees.plugins.credentials.common.StandardUsernamePasswordCredentials;
import com.cloudbees.plugins.credentials.domains.Domain;
import com.cloudbees.plugins.credentials.impl.BaseStandardCredentials;
import com.google.common.base.Strings;

import edu.umd.cs.findbugs.annotations.NonNull;
import hudson.Extension;
import hudson.Util;
import hudson.model.AbstractBuild;
import hudson.model.AbstractDescribableImpl;
import hudson.model.AbstractProject;
import hudson.model.BuildableItemWithBuildWrappers;
import hudson.model.Descriptor;
import hudson.model.Item;
import hudson.model.ItemGroup;
import hudson.security.ACL;
import hudson.util.FormValidation;
import hudson.util.Secret;
import io.plugins.perfecto.PerfectoBuildWrapper;
import jenkins.model.Jenkins;


/**
 * Perfecto credentials class
 *
 * @author Dushyantan Satike, Genesis
 */
public class PerfectoCredentials extends BaseStandardCredentials implements StandardUsernamePasswordCredentials {


	protected String userName;
	protected String cloudName;
	protected Secret apiKey;
	private static final String ERR_EMPTY_AUTH = "Empty username or cloudname or security token!";
	private static final String ERR_INVALID_AUTH = "Invalid username or cloudname or security token!";
	private static final String OK_VALID_AUTH = "Success";

	protected ShortLivedConfig shortLivedConfig;
	static String regex = "^[^>|;\\{}()\\&&<^]*$";

	@DataBoundConstructor
	public PerfectoCredentials(@CheckForNull CredentialsScope scope, @CheckForNull String id,  String userName, @CheckForNull String cloudName,
			@CheckForNull String apiKey, @CheckForNull String description) {
		super(scope, id, description);
		if(userName.trim() != null) {
			if(userName.trim().matches("^.{1,50}$") && (userName.trim().matches(regex))) {
				this.userName = userName;
			}
			else {
				throw new IllegalArgumentException("Username seems to be empty.");
			}
		}
		else {
			throw new IllegalArgumentException("Username is null");
					}
			if(cloudName.trim() != null && (cloudName.trim().matches(regex))) {
				if(cloudName.trim().matches("[\\w.-]{0,19}")) {
					this.cloudName = cloudName;
				}else {
					throw new IllegalArgumentException("Cloud Name doesnt seem to be valid.");
				}
			}else {
				throw new IllegalArgumentException("Cloud Name is null");
			}
			if(apiKey.trim() != null) {
				if(!apiKey.trim().isEmpty() && (apiKey.trim().matches(regex))){
					this.apiKey = Secret.fromString(apiKey);
				}else {
					throw new IllegalArgumentException("Security Token seems to be empty.");
				}
			}else {
				throw new IllegalArgumentException("Security Token is null");
			}
		}

		public ShortLivedConfig getShortLivedConfig() {
			return shortLivedConfig;
		}

		@DataBoundSetter
		public void setShortLivedConfig(ShortLivedConfig shortLivedConfig) {
			this.shortLivedConfig = shortLivedConfig;
		}

		public static PerfectoCredentials getCredentials(AbstractProject project) {
			if (project == null) { return null; }

			if (!(project instanceof BuildableItemWithBuildWrappers)) {
				return getCredentials((AbstractProject) project.getParent());
			}
			BuildableItemWithBuildWrappers p = (BuildableItemWithBuildWrappers) project;
			PerfectoBuildWrapper bw = p.getBuildWrappersList().get(PerfectoBuildWrapper.class);
			if (bw == null) { return null; }
			String credentialsId = bw.getCredentialId();
			return getCredentialsById((Item) p, credentialsId);
		}

		public static FormValidation testAuthentication(final String username, final String cloudName, final String apikey) {
			String checkConnectionURL = "https://"+cloudName+".perfectomobile.com/services/users/"+username+"?operation=info&securityToken="+apikey;
			URL myURL;
			HttpsURLConnection conn = null;
			try {
				myURL = new URL(checkConnectionURL);
				conn = (HttpsURLConnection) myURL.openConnection();
				conn.setRequestMethod("POST");
				conn.setRequestProperty("Accept", "application/json");
				int response = conn.getResponseCode();
				System.out.println("response"+response);
				if (response != 200) {
					conn.disconnect();
					return FormValidation.error(ERR_INVALID_AUTH+", HTTP error code : "+response);
				}
				conn.disconnect();
			}catch(Exception e) {
				if(conn != null) {
					conn.disconnect();
				}
				System.out.println("exception: "+e);
				return FormValidation.error(ERR_INVALID_AUTH);
			}
			System.out.println("success");
			return FormValidation.ok(OK_VALID_AUTH);
		}

		public static PerfectoCredentials getCredentials(AbstractBuild build) {
			return getCredentials(build.getProject());
		}

		@NonNull
		public Secret getPassword() {
			if (getShortLivedConfig() != null) {
				try {
					Date d = new Date();
					Date expires = new Date(
							System.currentTimeMillis() +
							(long) getShortLivedConfig().getTime() * 1000 /* to millis */ * 60 /* to minutes */
							);
					String token = JWT.create().withExpiresAt(expires).withIssuedAt(d).sign(com.auth0.jwt.algorithms.Algorithm.HMAC256(apiKey.getPlainText()));
					return Secret.fromString(token);
				} catch (JWTCreationException e){
					//Invalid Signing configuration / Couldn't convert Claims.
					e.printStackTrace();
				} 
			}
			return getApiKey();
		}

		@NonNull
		public String getUserName() {
			return userName;
		}

		@NonNull
		public Secret getApiKey() {
			return apiKey;
		}

		public static PerfectoCredentials getPerfectoCredentials(AbstractBuild build, PerfectoBuildWrapper wrapper) {
			String credentialId = wrapper.getCredentialId();
			return getCredentialsById(build.getProject(), credentialId);
		}

		public String getCloudName() {
			return cloudName;
		}

		@Extension(ordinal = 1.0D)
		public static class DescriptorImpl extends CredentialsDescriptor
		{
			@Override
			public String getDisplayName() {
				return "Perfecto";
			}

			@Override
			public String getIconClassName() {
				return "icon-perfecto-credential";
			}

			@POST
			public final FormValidation doAuthenticate(@QueryParameter("userName") String userName, @QueryParameter("cloudName") String cloudName,
					@QueryParameter("apiKey") String apiKey) {
				Jenkins.get().checkPermission(Jenkins.ADMINISTER);
				if (StringUtils.isBlank(userName) || StringUtils.isBlank(cloudName) || StringUtils.isBlank(apiKey)) {
					return FormValidation.error(ERR_EMPTY_AUTH);
				}
				return testAuthentication(userName, cloudName, apiKey);
			}

			@POST
			public FormValidation doCheckCloudName(@QueryParameter String value) {
				Jenkins.get().checkPermission(Jenkins.ADMINISTER);
				if (Util.fixEmptyAndTrim(value) == null) {
					return FormValidation.error("Cloud Name cannot be empty");
				}
				if(!value.matches("[\\w.-]{0,19}") && (!(value.trim()).matches(regex))) {
					return FormValidation.error("Cloud Name doesnt seem to be valid.");
				}
				return FormValidation.ok();
			}


			@POST
			public FormValidation doCheckApiKey(@QueryParameter String value) {
				Jenkins.get().checkPermission(Jenkins.ADMINISTER);
				if (Util.fixEmptyAndTrim(value) == null) {
					return FormValidation.error("Security Token cannot be empty");
				}
				if(!value.trim().matches(regex)) {
					return FormValidation.error("security token  doesnt seem to be valid.");
				}
				return FormValidation.ok();
			}

			@POST
			public FormValidation doCheckUserName(@QueryParameter String value) {
				Jenkins.get().checkPermission(Jenkins.ADMINISTER);
				if (Util.fixEmptyAndTrim(value) == null) {
					return FormValidation.error("Username cannot be empty");
				}
				if((!value.trim().matches(regex))) {
					return FormValidation.error("User Name doesnt seem to be valid.");
				}
				return FormValidation.ok();
			}
		}

		public static String migrateToCredentials(String username, String cloudName, String accessKey, String migratedFrom) throws InterruptedException, IOException {
			final List<PerfectoCredentials> credentialsForDomain = PerfectoCredentials.all((Item) null);
			final StandardUsernameCredentials existingCredentials = CredentialsMatchers.firstOrNull(
					credentialsForDomain,
					CredentialsMatchers.withUsername(username)
					);

			final String credentialId;
			if (existingCredentials == null) {
				String createdCredentialId = UUID.randomUUID().toString();

				final StandardUsernameCredentials credentialsToCreate;
				if (!Strings.isNullOrEmpty(accessKey)) {
					credentialsToCreate = new PerfectoCredentials(
							CredentialsScope.GLOBAL,
							createdCredentialId,
							username,
							cloudName,
							accessKey,
							"migrated from " + migratedFrom
							);
				} else {
					throw new InterruptedException("Did not find password");
				}

				final SystemCredentialsProvider credentialsProvider = SystemCredentialsProvider.getInstance();
				final Map<Domain, List<Credentials>> credentialsMap = credentialsProvider.getDomainCredentialsMap();

				final Domain domain = Domain.global();
				if (credentialsMap.get(domain) == null) {
					credentialsMap.put(domain, Collections.EMPTY_LIST);
				}
				credentialsMap.get(domain).add(credentialsToCreate);

				credentialsProvider.setDomainCredentialsMap(credentialsMap);
				credentialsProvider.save();

				credentialId = createdCredentialId;
			} else {
				credentialId = existingCredentials.getId();
			}

			return credentialId;
		}

		public static List<PerfectoCredentials> all(ItemGroup context) {
			return CredentialsProvider.lookupCredentials(
					PerfectoCredentials.class,
					context,
					ACL.SYSTEM
					);
		}

		public static List<PerfectoCredentials> all(Item context) {
			return CredentialsProvider.lookupCredentials(
					PerfectoCredentials.class,
					context,
					ACL.SYSTEM
					);
		}

		public static PerfectoCredentials getCredentialsById(Item context, String id) {
			return CredentialsMatchers.firstOrNull(
					PerfectoCredentials.all((Item) context),
					CredentialsMatchers.withId(id)
					);
		}

		public static final class ShortLivedConfig extends AbstractDescribableImpl<ShortLivedConfig> implements Serializable {
			protected final Integer time;

			@DataBoundConstructor
			public ShortLivedConfig(Integer time) {
				this.time = time;
			}

			public Integer getTime() {
				return time;
			}

			@Extension
			public static class DescriptorImpl extends Descriptor<ShortLivedConfig> {
				@Override
				public String getDisplayName() { return ""; }
			}

		}

		@Override
		public String getUsername() {
			// TODO Auto-generated method stub
			return "";
		}

	}
