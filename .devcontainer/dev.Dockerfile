# .devcontainer/dev.Dockerfile
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ---- Base OS deps (keep these in ONE layer) ----
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
    unzip \
    tar \
    sudo \
    lsb-release \
    software-properties-common \
    apt-transport-https \
    vim \
    nano \
    jq \
    ripgrep \
    tree \
    docker.io \
    zsh \
    # needed for add-apt-repository / PPAs
    gnupg \
    gpg-agent \
    dirmngr \
    # build deps for common Python wheels
    build-essential \
    pkg-config \
    # keep system python tooling happy
    python3 \
    python3-venv \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ---- Python 3.12 (Patcher requirement) ----
# IMPORTANT: do NOT change /usr/bin/python3 (apt tooling depends on system python3-apt)
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       python3.12 \
       python3.12-venv \
       python3.12-dev \
    && rm -rf /var/lib/apt/lists/*

# Ensure pip exists for Python 3.12 (separate from system pip)
RUN python3.12 -m ensurepip --upgrade \
    && python3.12 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Optional convenience: make `python` be Python 3.12 (leave `python3` alone!)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# ---- Java toolchains (dev convenience) ----
RUN add-apt-repository ppa:openjdk-r/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       openjdk-8-jdk \
       openjdk-11-jdk \
       openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-1.17.0-openjdk-amd64

# ---- Maven (multiple versions) ----
ENV MAVEN_DIR=/opt/maven
ARG MAVEN_VERSIONS="3.2.1 3.5.0 3.9.8"
RUN mkdir -p "${MAVEN_DIR}" && \
    for version in ${MAVEN_VERSIONS}; do \
      wget -q "https://archive.apache.org/dist/maven/maven-3/${version}/binaries/apache-maven-${version}-bin.tar.gz" -O "/tmp/maven-${version}.tgz" && \
      tar -xzf "/tmp/maven-${version}.tgz" -C "${MAVEN_DIR}" && \
      rm -f "/tmp/maven-${version}.tgz"; \
    done

ENV MAVEN_HOME=${MAVEN_DIR}/apache-maven-3.9.8
ENV PATH=${MAVEN_HOME}/bin:${PATH}

# ---- Gradle (multiple versions) ----
ENV GRADLE_DIR=/opt/gradle
ARG GRADLE_VERSIONS="6.8.2 7.6.4 8.9"
RUN mkdir -p "${GRADLE_DIR}" && \
    for version in ${GRADLE_VERSIONS}; do \
      wget -q "https://services.gradle.org/distributions/gradle-${version}-bin.zip" -O "/tmp/gradle-${version}.zip" && \
      unzip -q "/tmp/gradle-${version}.zip" -d "${GRADLE_DIR}" && \
      rm -f "/tmp/gradle-${version}.zip"; \
    done

ENV GRADLE_HOME=${GRADLE_DIR}/gradle-8.9
ENV PATH=${GRADLE_HOME}/bin:${PATH}

# ---- Create a non-root dev user ----
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" -s /bin/bash \
    && usermod -aG sudo,docker "${USERNAME}" \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Quick sanity checks
RUN python3 --version && python3.12 --version && python --version && \
    python3.12 -m pip --version && \
    java -version && mvn -version && gradle --version && docker --version

WORKDIR /workspaces/autosec
USER ${USERNAME}

CMD ["/bin/bash"]
