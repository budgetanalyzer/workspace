# Use the pinned Ubuntu 24.04 digest. Keep this digest-only because the
# Dev Containers image resolver rejects tag+digest base references.
FROM docker.io/library/ubuntu@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3

ARG TARGETARCH
ARG NODE_MAJOR=24
ARG KUBECTL_VERSION=v1.35.4
ARG HELM_VERSION=v3.22.0
ARG TILT_VERSION=0.37.3
ARG MITMPROXY_VERSION=12.2.3
ARG ACTIONLINT_VERSION=1.7.12
ARG VIA_VERSION=3.0.13
ARG VIA_URL=https://www.robots.ox.ac.uk/~vgg/software/via/downloads/via3/via-3.0.13.zip
ARG VIA_ARCHIVE_SHA256=d16fac5ac83507587845c04644bdbe81896865f2cb963d570bf0f52d48e7d793
ARG VIA_ASSET_SHA256=44de1edcee45a0c442dcd028316cdce1647b4fb1a3ca3669b07cd77f39e5fc98

ENV DEBIAN_FRONTEND=noninteractive
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

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
    # Chromium uses the vscode user's NSS database for locally added roots
    libnss3-tools \
    vim \
    poppler-utils \
    # Deterministic image inspection, cropping, and review overlays
    imagemagick \
    tree \
    # Networking tools for DNS/email debugging
    dnsutils \
    iputils-ping \
    traceroute \
    netcat-openbsd \
    # Python package management
    python3-pip \
    # Shell script linting
    shellcheck \
    # Extract the pinned VIA standalone distribution
    unzip \
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

# Install the official standalone VGG Image Annotator release. VIA is a
# human-operated BSD-2-Clause annotation tool; it is not an automatic tracer.
# Verify both the versioned upstream archive and the installed image annotator.
RUN set -eux; \
    curl -fsSLo /tmp/via-annotator.zip "${VIA_URL}"; \
    echo "${VIA_ARCHIVE_SHA256}  /tmp/via-annotator.zip" | sha256sum -c -; \
    mkdir -p /tmp/via-annotator-extracted /opt/via-annotator; \
    unzip -q /tmp/via-annotator.zip -d /tmp/via-annotator-extracted; \
    echo "${VIA_ASSET_SHA256}  /tmp/via-annotator-extracted/via-${VIA_VERSION}/via_image_annotator.html" | sha256sum -c -; \
    install -m 0444 "/tmp/via-annotator-extracted/via-${VIA_VERSION}/via_image_annotator.html" /opt/via-annotator/via_image_annotator.html; \
    install -m 0444 "/tmp/via-annotator-extracted/via-${VIA_VERSION}/LICENSE" /opt/via-annotator/LICENSE; \
    install -m 0444 "/tmp/via-annotator-extracted/via-${VIA_VERSION}/README.md" /opt/via-annotator/README.md; \
    chmod 0555 /opt/via-annotator; \
    rm -rf /tmp/via-annotator.zip /tmp/via-annotator-extracted

# Install Azul Zulu OpenJDK 25
RUN apt-get update && apt-get install -y gnupg ca-certificates curl \
    && curl -s https://repos.azul.com/azul-repo.key | gpg --dearmor -o /usr/share/keyrings/azul.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/azul.gpg] https://repos.azul.com/zulu/deb stable main" > /etc/apt/sources.list.d/zulu.list \
    && apt-get update \
    && apt-get install -y zulu25-jdk \
    && ln -sfn "/usr/lib/jvm/zulu25-ca-${TARGETARCH}" /usr/lib/jvm/zulu25 \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/zulu25
ENV PATH=$JAVA_HOME/bin:$PATH

# Install Maven via apt (more reliable than manual download)
RUN apt-get update && apt-get install -y maven \
    && rm -rf /var/lib/apt/lists/*

ENV MAVEN_HOME=/usr/share/maven
ENV PATH=$MAVEN_HOME/bin:$PATH

# Install Go
RUN curl -fsSL https://go.dev/dl/go1.24.1.linux-amd64.tar.gz | tar -C /usr/local -xz
ENV PATH=/usr/local/go/bin:$PATH

# Install actionlint
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) actionlint_sha256='8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8' ;; \
        arm64) actionlint_sha256='325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6' ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /tmp/actionlint.tar.gz "https://github.com/rhysd/actionlint/releases/download/v${ACTIONLINT_VERSION}/actionlint_${ACTIONLINT_VERSION}_linux_${TARGETARCH}.tar.gz"; \
    echo "${actionlint_sha256}  /tmp/actionlint.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/actionlint.tar.gz -C /usr/local/bin actionlint; \
    chmod +x /usr/local/bin/actionlint; \
    rm -f /tmp/actionlint.tar.gz

# Install kubectl
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64) kubectl_sha256='b529430df69a688fd61b64ad2299edb5fd71cb58be2a4779dba624c7d3510efd' ;; \
        arm64) kubectl_sha256='6a5a4cc4e396d7626a7a693a3044b51c75520f81db30fe6816c2554e53be336f' ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${TARGETARCH}/kubectl"; \
    echo "${kubectl_sha256}  /usr/local/bin/kubectl" | sha256sum -c -; \
    chmod +x /usr/local/bin/kubectl

# Install kind
RUN set -eux; \
    case "${TARGETARCH}" in \
        amd64|arm64) : ;; \
        *) echo "Unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSLo /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/v0.31.0/kind-linux-${TARGETARCH}" \
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
        amd64) tilt_arch='x86_64'; tilt_sha256='e90bc6cf70882bc7579d8174a27cab2de0284612ec7339e4b32f669cd5de4e5c' ;; \
        arm64) tilt_arch='arm64'; tilt_sha256='826f48198f368ef5edb684e9ae4c87ff76eca84c904f72b2376b29b93bffc019' ;; \
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
# AI CODING CLIs (installed globally as root)
# =======================================================

ARG CLI_CACHE_BUST=0

# Claude Code (npm - deprecated but required for proxy support)
# Native binary (Bun) ignores HTTP_PROXY for streaming: github.com/anthropics/claude-code/issues/14165
RUN set -eux; \
    echo "Refreshing AI coding CLIs with cache bust ${CLI_CACHE_BUST}"; \
    npm install -g \
        @anthropic-ai/claude-code@latest \
        @openai/codex@latest \
        @google/gemini-cli@latest

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

# Create auth/config directories for the container user. Codex lean defaults
# are passed by the codex-lean launcher so plain codex keeps upstream defaults.
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
COPY scripts/codex-lean.sh /usr/local/bin/codex-lean
COPY scripts/codex-with-proxy.sh /usr/local/bin/codex-with-proxy
COPY scripts/codex-max-with-proxy.sh /usr/local/bin/codex-max-with-proxy
COPY scripts/ensure-budget-analyzer-local-ca-trust.sh /usr/local/bin/ensure-budget-analyzer-local-ca-trust
COPY scripts/check-budget-analyzer-local-ca-trust.sh /usr/local/bin/check-budget-analyzer-local-ca-trust
COPY scripts/via-annotator.sh /usr/local/bin/via-annotator
COPY scripts/ai-run.sh /usr/local/bin/ai-run
RUN chmod +x /usr/local/bin/start-proxy /usr/local/bin/claude-with-proxy \
    /usr/local/bin/mitmflows /usr/local/bin/mitmflow-detail /usr/local/bin/mitmflow-body \
    /usr/local/bin/mitmflow-render.py /usr/local/bin/claude-with-custom-system-prompt \
    /usr/local/bin/claude-45-custom-system-prompt /usr/local/bin/claude-46-custom-system-prompt \
    /usr/local/bin/codex-lean /usr/local/bin/codex-with-proxy /usr/local/bin/codex-max-with-proxy \
    /usr/local/bin/ensure-budget-analyzer-local-ca-trust /usr/local/bin/check-budget-analyzer-local-ca-trust \
    /usr/local/bin/via-annotator /usr/local/bin/ai-run

# Switch to non-root user
USER $USERNAME
ENV PATH=/home/${USERNAME}/.local/bin:${PATH}

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
