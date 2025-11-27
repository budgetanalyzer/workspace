# Budget Analyzer Ecosystem

Navigation map for AI agents exploring this workspace.

## Services

| Repo | Purpose |
|------|---------|
| orchestration/ | System coordination, deployment, cross-cutting concerns |
| transaction-service/ | Transaction domain API |
| currency-service/ | Currency conversion API |
| permission-service/ | Authorization and roles |
| session-gateway/ | BFF for browser security |
| token-validation-service/ | JWT validation for NGINX |

## Frontend

| Repo | Purpose |
|------|---------|
| budget-analyzer-web/ | React frontend application |

## Shared

| Repo | Purpose |
|------|---------|
| service-common/ | Shared Spring Boot patterns and utilities |
| checkstyle-config/ | Code style rules for Java services |

## Meta

| Repo | Purpose |
|------|---------|
| architecture-conversations/ | Architectural discourse and patterns |

## Navigation Patterns

**Starting points by intent:**

- **Run the system**: Start with `orchestration/CLAUDE.md`
- **Understand architecture decisions**: Start with `architecture-conversations/conversations/INDEX.md`
- **Work on a service**: Navigate directly to `{service-name}/CLAUDE.md`
- **Understand shared patterns**: Start with `service-common/CLAUDE.md`

**Discovery commands:**

```bash
# List all repos
ls -d /workspace/*/

# Find all CLAUDE.md files
find /workspace -maxdepth 2 -name "CLAUDE.md" -type f

# Quick health check on services
kubectl get pods -n budget-analyzer
```
