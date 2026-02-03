# .devcontainer/dev.Dockerfile
FROM ubuntu:24.04

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
    gnupg \
    dirmngr \
    build-essential \
    pkg-config \
    # Python 3.12 is the default on Ubuntu 24.04
    python3 \
    python3-venv \
    python3-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Optional convenience: make `python` point to Python 3.12 (leave `python3` alone)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# ---- Java toolchains: Temurin 8/11/17 (recommended for Ubuntu 24.04) ----
# Ubuntu 24.04 doesn't ship OpenJDK 8 cleanly; use Adoptium repo.
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public \
      | gpg --dearmor -o /etc/apt/keyrings/adoptium.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.gpg] https://packages.adoptium.net/artifactory/deb $(. /etc/os-release && echo $VERSION_CODENAME) main" \
      > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       temurin-8-jdk \
       temurin-11-jdk \
       temurin-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set default Java to 17 (you can switch in-container with update-alternatives if needed)
RUN update-alternatives --set java /usr/lib/jvm/temurin-17-jdk-amd64/bin/java || true
ENV JAVA_HOME=/usr/lib/jvm/temurin-17-jdk-amd64
ENV PATH=${JAVA_HOME}/bin:${PATH}

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

# ---- Create vscode user (no UID/GID pinning; Dev Containers will remap as needed) ----
RUN set -eux; \
    getent group docker >/dev/null || groupadd docker; \
    id -u vscode >/dev/null 2>&1 || useradd -m -s /bin/bash vscode; \
    usermod -aG sudo,docker vscode; \
    echo "vscode ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/vscode; \
    chmod 0440 /etc/sudoers.d/vscode

# Quick sanity checks
RUN python3 --version && python --version && \
    python3 -m pip --version && \
    java -version && \
    /usr/lib/jvm/temurin-8-jdk-amd64/bin/java -version && \
    /usr/lib/jvm/temurin-11-jdk-amd64/bin/java -version && \
    mvn -version && gradle --version && docker --version

WORKDIR /workspaces/autosec
CMD ["/bin/bash"]