# Use Ubuntu 24.04 as base image (explicit registry reference)
FROM docker.io/library/ubuntu:24.04@sha256:186072bba1b2f436cbb91ef2567abca677337cfc786c86e107d25b7072feef0c

ARG TARGETARCH
ARG NODE_MAJOR=20
ARG HELM_VERSION=v3.20.1
ARG TILT_VERSION=0.37.0
ARG MITMPROXY_VERSION=12.2.2

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
    poppler-utils \
    # Networking tools for DNS/email debugging
    dnsutils \
    iputils-ping \
    traceroute \
    netcat-openbsd \
    # Python package management
    python3-pip \
    # Shell script linting
    shellcheck \
    # mitmproxy install dependency
    pipx \
    bubblewrap \
    && rm -rf /var/lib/apt/lists/*

# Install common Python libraries
RUN pip3 install --no-cache-dir --break-system-packages pyyaml

# Install Node.js (pinned major line via signed NodeSource apt repo)
RUN mkdir -p /etc/apt/keyrings \
    && curl -fsSLo /tmp/nodesource.gpg.key https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    && gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg /tmp/nodesource.gpg.key \
    && rm -f /tmp/nodesource.gpg.key \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
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

# Install Go
RUN curl -fsSL https://go.dev/dl/go1.24.1.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH=/usr/local/go/bin:$PATH

# Install kubectl
RUN curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg \
    && echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' > /etc/apt/sources.list.d/kubernetes.list \
    && apt-get update \
    && apt-get install -y kubectl \
    && rm -rf /var/lib/apt/lists/*

# Install kind
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64|arm64) : ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/v0.24.0/kind-linux-${TARGETARCH}" \
    && chmod +x /usr/local/bin/kind

# Install helm
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) helm_sha256='0165ee4a2db012cc657381001e593e981f42aa5707acdd50658326790c9d0dc3' ;; \
        arm64) helm_sha256='56b9d1b0e0efbb739be6e68a37860ace8ec9c7d3e6424e3b55d4c459bc3a0401' ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /tmp/helm.tar.gz "https://get.helm.sh/helm-${HELM_VERSION}-linux-${TARGETARCH}.tar.gz"; \
    echo "${helm_sha256}  /tmp/helm.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/helm.tar.gz -C /tmp; \
    mv "/tmp/linux-${TARGETARCH}/helm" /usr/local/bin/helm; \
    chmod +x /usr/local/bin/helm; \
    rm -rf /tmp/helm.tar.gz "/tmp/linux-${TARGETARCH}"

# Install tilt
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) tilt_arch='x86_64'; tilt_sha256='c2c7d3649233f01bc5d230b66b8ccd332401f348dc22b863fcf7244da6970ff1' ;; \
        arm64) tilt_arch='arm64'; tilt_sha256='84457137539d8e4be6e90e9afecf8ef692ad3f8c19e9bf3355f3fbf4f8dce55f' ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /tmp/tilt.tar.gz "https://github.com/tilt-dev/tilt/releases/download/v${TILT_VERSION}/tilt.${TILT_VERSION}.linux.${tilt_arch}.tar.gz"; \
    echo "${tilt_sha256}  /tmp/tilt.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/tilt.tar.gz -C /usr/local/bin tilt; \
    rm -f /tmp/tilt.tar.gz

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

# =======================================================
# PLAYWRIGHT (headless browser for scraping / automation)
# =======================================================

# Install Playwright npm package globally
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN npm install -g playwright

# Install Chromium system dependencies (shared libs like libgbm, libasound, etc.)
RUN npx playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Download Chromium binary to shared path, readable by all users
RUN mkdir -p ${PLAYWRIGHT_BROWSERS_PATH} \
    && npx playwright install chromium \
    && chmod -R o+rx ${PLAYWRIGHT_BROWSERS_PATH}

# Set up working directory with proper ownership
RUN mkdir -p /workspace && chown -R $USER_UID:$USER_GID /workspace

# Create config directories for the container user
RUN mkdir -p /home/$USERNAME/.codex && chown -R $USER_UID:$USER_GID /home/$USERNAME/.codex
RUN mkdir -p /home/$USERNAME/.gemini && chown -R $USER_UID:$USER_GID /home/$USERNAME/.gemini

# Copy entrypoint and helper scripts
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh
COPY scripts/start-proxy.sh /usr/local/bin/start-proxy
COPY scripts/claude-with-proxy.sh /usr/local/bin/claude-with-proxy
COPY scripts/claude-with-custom-system-prompt.sh /usr/local/bin/claude-with-custom-system-prompt
COPY scripts/claude-45-custom-system-prompt.sh /usr/local/bin/claude-45-custom-system-prompt
COPY scripts/claude-46-custom-system-prompt.sh /usr/local/bin/claude-46-custom-system-prompt
COPY scripts/mitmflows /usr/local/bin/mitmflows
COPY scripts/mitmflow-detail /usr/local/bin/mitmflow-detail
COPY scripts/mitmflow-body /usr/local/bin/mitmflow-body
COPY scripts/mitmflow-render.py /usr/local/bin/mitmflow-render.py
COPY scripts/codex-with-proxy.sh /usr/local/bin/codex-with-proxy
COPY scripts/codex-high-with-proxy.sh /usr/local/bin/codex-high-with-proxy
COPY scripts/codex-max-with-proxy.sh /usr/local/bin/codex-max-with-proxy
COPY scripts/codex-54-with-proxy.sh /usr/local/bin/codex-54-with-proxy
COPY scripts/codex-54-mini-with-proxy.sh /usr/local/bin/codex-54-mini-with-proxy
COPY scripts/codex-53-with-proxy.sh /usr/local/bin/codex-53-with-proxy
COPY scripts/codex-mini-with-proxy.sh /usr/local/bin/codex-mini-with-proxy
RUN chmod +x /usr/local/bin/start-proxy /usr/local/bin/claude-with-proxy \
    /usr/local/bin/mitmflows /usr/local/bin/mitmflow-detail /usr/local/bin/mitmflow-body \
    /usr/local/bin/mitmflow-render.py /usr/local/bin/claude-with-custom-system-prompt \
    /usr/local/bin/claude-45-custom-system-prompt /usr/local/bin/claude-46-custom-system-prompt \
    /usr/local/bin/codex-with-proxy /usr/local/bin/codex-high-with-proxy /usr/local/bin/codex-max-with-proxy \
    /usr/local/bin/codex-54-with-proxy /usr/local/bin/codex-54-mini-with-proxy \
    /usr/local/bin/codex-53-with-proxy /usr/local/bin/codex-mini-with-proxy

# Switch to non-root user
USER $USERNAME

# =======================================================
# MITMPROXY for HTTPS traffic inspection
# =======================================================

# Install mitmproxy via pipx (isolated from system Python)
RUN pipx install "mitmproxy==${MITMPROXY_VERSION}" && pipx ensurepath

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
