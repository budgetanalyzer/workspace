# Use Ubuntu 24.04 as base image (explicit registry reference)
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install essential packages
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    sudo \
    ca-certificates \
    gnupg \
    lsb-release \
    build-essential \
    vim \
    # Networking tools for DNS/email debugging
    dnsutils \
    iputils-ping \
    traceroute \
    netcat-openbsd \
    # mitmproxy install dependency
    pipx \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (latest LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Azul Zulu OpenJDK 24
RUN apt-get update && apt-get install -y gnupg ca-certificates curl \
    && curl -s https://repos.azul.com/azul-repo.key | gpg --dearmor -o /usr/share/keyrings/azul.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/azul.gpg] https://repos.azul.com/zulu/deb stable main" > /etc/apt/sources.list.d/zulu.list \
    && apt-get update \
    && apt-get install -y zulu24-jdk \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/zulu24
ENV PATH=$JAVA_HOME/bin:$PATH

# Install Maven via apt (more reliable than manual download)
RUN apt-get update && apt-get install -y maven \
    && rm -rf /var/lib/apt/lists/*

ENV MAVEN_HOME=/usr/share/maven
ENV PATH=$MAVEN_HOME/bin:$PATH

# Install kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' > /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y kubectl \
    && rm -rf /var/lib/apt/lists/*

# Install kind
RUN curl -Lo /usr/local/bin/kind https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-amd64 \
    && chmod +x /usr/local/bin/kind

# Install helm
RUN curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install tilt
RUN curl -fsSL https://raw.githubusercontent.com/tilt-dev/tilt/master/scripts/install.sh | bash

# Create vscode user with matching UID/GID from host
ARG USERNAME=vscode
ARG USER_UID
ARG USER_GID

# Create vscode group and user
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m -s /bin/bash $USERNAME \
    && echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Set up bash aliases for vscode user
COPY bash_aliases.sh /home/$USERNAME/.bash_aliases
RUN chown $USER_UID:$USER_GID /home/$USERNAME/.bash_aliases

# =======================================================
# AI CODING CLIs (all installed globally as root, cached in image layer)
# =======================================================

# Claude Code (npm - deprecated but required for proxy support)
# Native binary (Bun) ignores HTTP_PROXY for streaming: github.com/anthropics/claude-code/issues/14165
RUN npm install -g @anthropic-ai/claude-code

# Codex CLI (OpenAI terminal agent, Apache 2.0)
RUN npm install -g @openai/codex

# Gemini CLI (Google terminal agent)
RUN npm install -g @google/gemini-cli

# Set up working directory with proper ownership
RUN mkdir -p /workspace && chown -R $USER_UID:$USER_GID /workspace

# Create config directories for the container user
RUN mkdir -p /home/$USERNAME/.anthropic && chown -R $USER_UID:$USER_GID /home/$USERNAME/.anthropic
RUN mkdir -p /home/$USERNAME/.codex && chown -R $USER_UID:$USER_GID /home/$USERNAME/.codex
RUN mkdir -p /home/$USERNAME/.gemini && chown -R $USER_UID:$USER_GID /home/$USERNAME/.gemini

# Copy entrypoint and helper scripts
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY scripts/start-proxy.sh /usr/local/bin/start-proxy
COPY scripts/claude-with-proxy.sh /usr/local/bin/claude-with-proxy
COPY scripts/mitmflows /usr/local/bin/mitmflows
COPY scripts/mitmflow-detail /usr/local/bin/mitmflow-detail
COPY scripts/mitmflow-body /usr/local/bin/mitmflow-body
RUN chmod +x /usr/local/bin/start-proxy /usr/local/bin/claude-with-proxy \
    /usr/local/bin/mitmflows /usr/local/bin/mitmflow-detail /usr/local/bin/mitmflow-body

# Switch to non-root user
USER $USERNAME

# =======================================================
# MITMPROXY for HTTPS traffic inspection
# =======================================================

# Install mitmproxy via pipx (isolated from system Python)
RUN pipx install mitmproxy && pipx ensurepath

# Bootstrap mitmproxy CA cert (generated on first run)
RUN /home/$USERNAME/.local/bin/mitmdump --set confdir=/home/$USERNAME/.mitmproxy -k -q & \
    sleep 3 && kill $! 2>/dev/null || true

# Trust the CA system-wide and for Node.js
RUN sudo cp /home/$USERNAME/.mitmproxy/mitmproxy-ca-cert.pem /usr/local/share/ca-certificates/mitmproxy.crt \
    && sudo update-ca-certificates

# Node.js ignores system CA store — this env var injects the mitmproxy CA
ENV NODE_EXTRA_CA_CERTS=/home/vscode/.mitmproxy/mitmproxy-ca-cert.pem

# Set working directory
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
