# Dependency Automation

**Status:** Local configuration and image-scan workflow prepared; automation is
not installed or active. Hosted acceptance is pending Phase 12.

The shared
[Budget Analyzer dependency-automation policy](https://github.com/budgetanalyzer/orchestration/blob/main/docs/dependency-automation.md)
owns scheduling, update-PR ownership, activation, cost, and failure handling.
Renovate is the sole update-PR owner, automerge remains disabled, and Dependabot
remains alert-only.

## Update discovery

`renovate.json` extends the shared orchestration preset. Renovate's native
Dockerfile manager covers the workspace Dockerfile, while repository-specific
regex managers identify version declarations embedded in ARGs and download
URLs:

| Source | Package identity | Representation and review boundary |
| --- | --- | --- |
| `NODE_MAJOR` | Node.js (`node-version`) | Major line only. NodeSource apt selects the current patch during a fresh build. |
| `KUBECTL_VERSION` | `kubernetes/kubernetes` | Version is coupled to amd64 and arm64 SHA-256 values. |
| `HELM_VERSION` | `helm/helm` | Version is coupled to amd64 and arm64 SHA-256 values. |
| `TILT_VERSION` | `tilt-dev/tilt` | Version is coupled to amd64 and arm64 SHA-256 values. |
| `MITMPROXY_VERSION` | `mitmproxy` on PyPI | The pipx package is exactly pinned. |
| `ACTIONLINT_VERSION` | `rhysd/actionlint` | Version is coupled to amd64 and arm64 SHA-256 values. |
| Go archive URL | Go (`golang-version`) | Exact release, but the URL is hard-coded to `linux-amd64`. |
| Kind download URL | `kubernetes-sigs/kind` | Exact release and TARGETARCH-aware URL, but the existing download has no checksum verification. |

Native managers also cover the Docker-in-Docker Dev Container feature and the
Actions, runner, and Trivy inputs in the evidence workflow.

The checksum-coupled and platform-sensitive records require Dependency
Dashboard approval. Renovate may propose a version, but reviewers must update
the complete checksum table and run the existing verification. A partial
proposal is expected to fail and must not be made mergeable by weakening a
checksum check.

### Digest-only Ubuntu base

The Dockerfile deliberately uses `docker.io/library/ubuntu@sha256:...` without
a tag because the Dev Containers resolver rejects tag-plus-digest base refs.
Renovate's native Dockerfile extraction sees a digest-only `ubuntu` record but
cannot infer that it belongs to Ubuntu 24.04; an ordinary digest lookup could
therefore follow the registry's default tag. That native record is disabled.

A repository regex manager instead couples the exact digest to the adjacent
`Ubuntu 24.04` comment. Its replacement template preserves the digest-only
`FROM` form, and every proposal is dashboard-approval-gated. Routine digest
refreshes must retain 24.04. A changed comment and digest for a later Ubuntu
release is a visible platform migration, not a routine refresh. Reviewers must
inspect the index and prove both `linux/amd64` and `linux/arm64` children before
accepting either kind of proposal.

The sandbox source is a read-only bind mount in a running development
container. The adjacent datasource comments requested during onboarding are
staged in `tmp/dependency-automation/proposed/ai-agent-sandbox.patch` for the
workspace owner to apply from the host. The functional extraction rules do not
depend on those comments, so local validation covers the current checkout.

## Workspace image evidence

`.github/workflows/workspace-image-security-evidence.yml` runs weekly and by
manual dispatch only. It does not run on pull requests. The job:

1. Reads the exact digest-only base from the Dockerfile and verifies that its
   registry index is the declared Ubuntu release family with amd64 and arm64
   children.
2. Performs a no-cache `linux/amd64` build from the same context used by Compose,
   without pushing or starting the result.
3. Downloads the Trivy database, retains an all-package inventory and a separate
   vulnerability report, and extracts Node, Zulu, and Go package versions when
   Trivy exposes them. The job requires Trivy's Go binary record to agree with
   the declared archive version; declaration alone does not prove the installed
   binary.
4. Uploads raw build, base-index, package, vulnerability, and scanner evidence
   for seven days even if an earlier step fails.

Vulnerability findings do not fail the scheduled evidence job. Build,
base-resolution, database-download, inventory, scan, platform, required-package,
or artifact-upload failures do fail it. The image is never pushed, no live
workspace or host credential mount is used, and the built image's entrypoint is
never started.

The safe local build equivalent is:

```bash
docker buildx build \
  --no-cache \
  --platform linux/amd64 \
  --file ai-agent-sandbox/Dockerfile \
  --build-arg USER_UID=10001 \
  --build-arg USER_GID=10001 \
  --tag workspace-dependency-scan:local \
  --load \
  ai-agent-sandbox
```

This is intentionally the `ai-agent-sandbox` context declared by
`ai-agent-sandbox/docker-compose.yml`. Do not substitute the repository root,
add live mounts, push the image, or run its entrypoint for dependency evidence.
The scan-only UID/GID 10001 avoids the Ubuntu base's existing `ubuntu` account
at 1000. Normal Dev Container builds continue to use the host values generated
by `ai-agent-sandbox/setup-env.sh`; the Compose fallback of 1000 collides when
that generated file is absent, which remains an existing setup limitation rather
than an image-scan reason to change account creation.

## Inventory limits

Unversioned `apt-get install` declarations do not provide patch targets for
Renovate. This includes the base utilities, Maven, ImageMagick, and the
`zulu25-jdk` package: the Dockerfile selects Zulu major 25, while Azul apt
selects the patch available at build time. Renovate's `java-version` datasource
uses Adoptium metadata and must not be presented as Azul Zulu coverage.

Node is similarly declared as major 24 and receives NodeSource patch updates
only through a fresh apt transaction. A cached image build is not evidence of
current apt packages, so the workflow uses `--no-cache`. The current container
baseline is Node 24, but that user-owned prerequisite predates this onboarding
and is not a Renovate-discovered upgrade.

The official VIA 3.0.13 archive and its two checked-in checksums have no
corresponding release/tag in the upstream GitHub repository, so standard
Renovate datasources do not provide a trustworthy update path. VIA remains an
explicit discovery gap and must retain both checksum checks during manual
review. Global npm packages installed as `latest`, unbounded PyPI installs, and
unpinned apt packages likewise have scan/rebuild coverage but no version-pin PR.

The exact Ubuntu base index supports ARM64, and several binary downloads use
`TARGETARCH`, but the Go URL is fixed to `linux-amd64`. Consequently, the
workflow's amd64 build and scan is not proof that the complete image works on
ARM64. Changing that architecture behavior is separate work.

## Local baseline evidence

On 2026-09-07, the rebuilt active container reported Node `v24.20.0`, npm
`11.19.0`, Go `1.24.1 linux/amd64`, and Zulu OpenJDK `25.0.4.1+1-LTS`. The
installed apt inventory included `nodejs 24.20.0-1nodesource1` and Zulu 25
packages at `25.0.4.1-1`. These are observations, not desired-version inputs.
The Dockerfile and README both select Node major 24.

The checked-in Ubuntu digest is a multi-platform Ubuntu 24.04 index with both
linux/amd64 and linux/arm64 children. A no-cache local `linux/amd64` build from
the Compose context completed on 2026-09-07 without starting or pushing the
image. Trivy 0.74.0 identified Ubuntu 24.04, 481 OS packages, Node
`24.20.0`, Zulu `25.0.4.1`, and the Go `1.24.1` binary package. The raw local
evidence is staged under `tmp/dependency-automation/local-image-scan/`; it is
temporary validation output rather than a checked-in report. Vulnerability
scanning reported 4,381 result rows, including 29 critical and 767 high rows,
while scanner and database operations completed. Counts include repeated Go
standard-library findings across installed binaries and are not unique-advisory
or review-parity totals. The existing backlog remains non-gating under the
shared policy.

A credential-free Renovate 44.65.5 lookup under Node 24 extracted 16 records
from 13 files: one Dev Container feature, one native digest-only Dockerfile
record, five workflow records, and nine regex-managed Dockerfile records. The
safe Ubuntu manager separately proposed the current 24.04 digest and a visible
26.04 major; its replacement preserves the digest-only form. Node 24 was current,
the Go source exposed maintained-line 1.24 and later lines, and PyPI exposed a
mitmproxy patch. The safe Ubuntu Docker lookup succeeded. GitHub-backed identities
were extracted but reported `github-token-required`; those lookups remain pending
Phase 12 rather than being reported as successful.

## Phase 12 operator handoff

The following remains pending because preparation neither publishes files nor
uses credentials or account settings:

- Repository: `budgetanalyzer/workspace`. Check: hosted Renovate full dry run
  after the shared preset and this consumer are published. Scope: the Ubuntu
  digest-only mapping, Node, Go, kubectl, Helm, Tilt, mitmproxy, actionlint,
  Kind, Dockerfile, and workflow Actions. Action: run the trusted read-only
  hosted validation and then onboard the free Renovate App. Proof: retain the
  run URL and logs showing the preset resolved, every declared identity was
  extracted, Ubuntu 24.04 digest proposals preserve digest-only syntax, and no
  fatal/error output occurred. GitHub-backed release lookups are expected to
  need that hosted context.
- Repository: `budgetanalyzer/workspace`. Check: Actions cost and hosted image
  evidence. Scope: the three-hour-capable no-cache development-image build,
  public image/package downloads, Trivy database, seven-day artifact, and
  standard Linux runner. Action: before enabling the schedule, confirm repository
  visibility, included Actions allowance, storage, and disabled paid overages;
  then manually dispatch the workflow from trusted `main`. Proof: retain the run
  URL, duration, source revision, artifact, exact base digest/index, complete
  build, Node/Zulu inventory, Go declaration/discovery result, and successful
  Trivy database and scan statuses. Stop for user direction if this requires
  spend.
- Repository: `budgetanalyzer/workspace`. Check: complete hosted public download
  path. Scope: Docker Hub's Ubuntu index, NodeSource, Azul, Go, GitHub release
  assets, PyPI/npm, Playwright, and Trivy databases. Reason: local public success
  does not prove the hosted network path, and no registry login is requested
  during preparation. Action: inspect strict hosted logs. Proof: every download
  and scan completes without hidden authentication, rate-limit, or partial-data
  failure; retain failures as gaps rather than adding credentials or bypasses.
- Repository: `budgetanalyzer/workspace`. Check: GitHub dependency graph and
  Dependabot alert settings. Action: enable the graph and alerts while keeping
  Dependabot version and overlapping security-update PRs disabled. Proof:
  preserve sanitized settings and alert evidence for the final cross-repository
  coverage report.

Renovate and Trivy do not establish lifecycle support. Node, Go, Java, Ubuntu,
Kubernetes, Helm, Kind, and other installed tools remain subject to the
quarterly human upstream-support review owned by the shared policy.
