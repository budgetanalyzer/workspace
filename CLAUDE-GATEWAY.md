# Budget Analyzer Ecosystem Gateway

**FOR AI AGENTS: EXECUTE, DO NOT EXPLAIN**

This file is executable protocol. When loaded:
1. Run environment detection IMMEDIATELY
2. Route based on result WITHOUT asking user
3. Only pause for user input when explicitly instructed

---

## Step 0: Environment Detection — EXECUTE IMMEDIATELY

Run this command NOW and capture the output:

```bash
if [ -n "$REMOTE_CONTAINERS" ] || ([ -f "/.dockerenv" ] && [ -d "/workspace" ]); then
  echo "ENV:DEVCONTAINER"
elif command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
  echo "ENV:DOCKER_ONLY"
else
  echo "ENV:NO_DOCKER"
fi
```

### Routing — execute based on output above

- **ENV:DEVCONTAINER** → Proceed to "Ecosystem Navigation" section below
- **ENV:DOCKER_ONLY** → Execute Step 0a (create sandbox files). After file creation, output the handoff text specified in Step 0a.
- **ENV:NO_DOCKER** → Execute Step 0b (install Docker instructions)

---

## Step 0a: Create a Sandbox (Docker-only users)

Create these files to set up a devcontainer:

```
~/claude-sandbox/
├── workspace/              # Your projects go here
└── .devcontainer/
    ├── devcontainer.json
    └── Dockerfile
```

**devcontainer.json:**
```json
{
  "name": "Claude Code Sandbox",
  "build": { "dockerfile": "Dockerfile" },
  "workspaceFolder": "/workspace",
  "workspaceMount": "source=${localWorkspaceFolder}/workspace,target=/workspace,type=bind,consistency=cached",
  "remoteUser": "vscode",
  "updateRemoteUserUID": true,
  "postCreateCommand": "echo 'Claude Code Sandbox ready. Run: claude'"
}
```

**Dockerfile:**
```dockerfile
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y curl wget git sudo ca-certificates gnupg build-essential && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*
RUN useradd -m -s /bin/bash vscode && echo "vscode ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
RUN npm install -g @anthropic-ai/claude-code
RUN mkdir -p /workspace && chown -R vscode:vscode /workspace
USER vscode
WORKDIR /workspace
```

**After creation, output:**

> Sandbox created at ~/claude-sandbox/
>
> Next: Exit VS Code → Open ~/claude-sandbox → Click "Reopen in Container" → Wait ~10 min for build

---

## Step 0b: Install Docker (no-Docker users)

**Output this message to the user:**

> Docker is required but not installed.
>
> **Install Docker Desktop:**
> - Windows/Mac: https://docker.com/products/docker-desktop
> - Linux: https://docs.docker.com/engine/install/
>
> **After installing:**
> 1. Start Docker Desktop (Windows/Mac) or the Docker service (Linux)
> 2. Wait for it to fully start (system tray icon stops animating)
> 3. Return here and say "ready" — I'll re-check and continue setup

**Then STOP and wait for user response.** Do not proceed until user confirms Docker is installed.

---

## Ecosystem Navigation

### Services

| Repo | Purpose |
|------|---------|
| orchestration/ | System coordination, deployment, cross-cutting concerns |
| transaction-service/ | Transaction domain API |
| currency-service/ | Currency conversion API |
| permission-service/ | Authorization and roles |
| session-gateway/ | BFF for browser security |
| token-validation-service/ | JWT validation for NGINX |

### Frontend

| Repo | Purpose |
|------|---------|
| budget-analyzer-web/ | React frontend application |

### Shared

| Repo | Purpose |
|------|---------|
| service-common/ | Shared Spring Boot patterns and utilities |
| checkstyle-config/ | Code style rules for Java services |

### Meta / Experimental

| Repo | Purpose |
|------|---------|
| architecture-conversations/ | Architectural discourse and patterns |
| claude-discovery/ | Experimental AI discovery tool |

---

## Navigation by Intent

| Intent | Starting Point |
|--------|----------------|
| Run the system | `orchestration/CLAUDE.md` |
| Understand architecture | `architecture-conversations/conversations/INDEX.md` |
| Work on a service | `{service-name}/CLAUDE.md` |
| Understand shared patterns | `service-common/CLAUDE.md` |

---

## The Six Archetypes

Every CLAUDE.md fits one of these patterns:

| Archetype | Role | When to Use |
|-----------|------|-------------|
| **meta** | Observes, captures discourse | Documentation repos, conversation capture |
| **coordinator** | Orchestrates, enables | DevOps, deployment configs, multi-service coordination |
| **platform** | Provides patterns others consume | Shared libraries, common utilities |
| **service** | Implements domain logic | Backend services, APIs, business logic |
| **interface** | Bridges users to system | Frontend apps, CLIs, user-facing tools |
| **experimental** | Tests hypotheses | Prototypes, methodology testing |

---

## Curated Conversations

These five conversations capture core insights:

| # | Topic | Core Insight |
|---|-------|--------------|
| [003](../architecture-conversations/conversations/003-externalized-cognition.md) | Externalized Cognition | CLAUDE.md files capture expert mental models |
| [019](../architecture-conversations/conversations/019-archetypes-and-scopes.md) | Archetypes and Scopes | Six stable patterns recur at every scope |
| [021](../architecture-conversations/conversations/021-self-programming-via-prose.md) | Self-Programming via Prose | LLMs can be "programmed" by forcing externalization |
| [023](../architecture-conversations/conversations/023-asking-not-telling.md) | Asking, Not Telling | You don't tell AI what to build - you ask, then correct |
| [029](../architecture-conversations/conversations/029-natural-language-programming.md) | Natural Language Programming | CLAUDE.md files are programs in natural language |

Full index: [architecture-conversations/conversations/INDEX.md](../architecture-conversations/conversations/INDEX.md)

---

## Discovery Commands

```bash
# List all repos
ls -d /workspace/*/

# Find all CLAUDE.md files
find /workspace -maxdepth 2 -name "CLAUDE.md" -type f

# Quick health check on services
kubectl get pods -n budget-analyzer
```
