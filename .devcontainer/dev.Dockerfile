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
    # build deps for common Python wheels
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ---- Python 3.12 (Ubuntu 22.04 needs deadsnakes) ----
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3.12-dev \
        python3.12-distutils \
    && rm -rf /var/lib/apt/lists/*

# Install pip for 3.12 (avoid relying on OS pip)
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12

# Make python3/pip3 resolve to 3.12 for consistency
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2 \
    && update-alternatives --install /usr/bin/pip3 pip3 /usr/local/bin/pip3 2

# ---- Java toolchains (Finder needs multiple) ----
RUN add-apt-repository ppa:openjdk-r/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends openjdk-8-jdk openjdk-11-jdk openjdk-17-jdk \
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

# ---- Miniconda (architecture-aware, same as Finder) ----
ENV CONDA_DIR=/opt/conda
ENV PATH=${CONDA_DIR}/bin:${PATH}

RUN ARCH="$(uname -m)" && \
    if [ "${ARCH}" = "x86_64" ]; then \
        CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"; \
    elif [ "${ARCH}" = "aarch64" ]; then \
        CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"; \
    else \
        echo "Unsupported architecture: ${ARCH}" && exit 1; \
    fi && \
    wget -q "${CONDA_URL}" -O /tmp/miniconda.sh && \
    chmod +x /tmp/miniconda.sh && \
    /tmp/miniconda.sh -b -p "${CONDA_DIR}" && \
    rm -f /tmp/miniconda.sh && \
    conda clean -afy

# Conda TOS (Finder notes this is required)
RUN conda tos accept

# ---- CodeQL (match Finder's expectation of a patched build) ----
ENV CODEQL_DIR=/opt/codeql
RUN mkdir -p "${CODEQL_DIR}" && \
    curl -L -o /tmp/codeql.zip \
      https://github.com/iris-sast/iris/releases/download/codeql-0.8.3-patched/codeql.zip && \
    unzip -qo /tmp/codeql.zip -d "${CODEQL_DIR}" && \
    rm -f /tmp/codeql.zip

ENV PATH=${CODEQL_DIR}/codeql:${CODEQL_DIR}:${PATH}

# ---- Create a non-root dev user ----
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=1000

RUN groupadd --gid "${USER_GID}" "${USERNAME}" \
    && useradd --uid "${USER_UID}" --gid "${USER_GID}" -m "${USERNAME}" -s /bin/bash \
    && usermod -aG sudo,docker "${USERNAME}" \
    && echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >/etc/sudoers.d/${USERNAME} \
    && chmod 0440 /etc/sudoers.d/${USERNAME}

# Make conda available in interactive shells for vscode user
RUN echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/${USERNAME}/.bashrc \
    && echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/${USERNAME}/.zshrc \
    && chown ${USERNAME}:${USERNAME} /home/${USERNAME}/.bashrc /home/${USERNAME}/.zshrc

# Quick sanity checks (fail fast if image breaks)
RUN python3 --version && pip3 --version && java -version && mvn -version && gradle --version && conda --version

WORKDIR /workspaces/autosec
USER ${USERNAME}

CMD ["/bin/bash"]
