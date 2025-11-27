# Use Ubuntu 24.04 as base image
FROM ubuntu:24.04

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

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Set up working directory with proper ownership
RUN mkdir -p /workspace && chown -R $USER_UID:$USER_GID /workspace

# Create .anthropic directory for the container user
RUN mkdir -p /home/$USERNAME/.anthropic && chown -R $USER_UID:$USER_GID /home/$USERNAME/.anthropic

# Copy entrypoint script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Switch to non-root user
USER $USERNAME

# Set working directory
WORKDIR /workspace

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
