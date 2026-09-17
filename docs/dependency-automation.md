# Dependency Automation

**Status:** The protected branch trial is active and Batch B is complete. The
public-Git-tag fallback for `aquasecurity/setup-trivy` passed its automatic
corrective Renovate cycle, and the resulting image-evidence run passed with
uploads skipped and zero artifacts. The workflow also accepts trusted
same-repository pull requests targeting `dependency-automation-trial` so the
Batch C representative bot PR receives the complete image check. The Phase 12
workspace correction is prepared from trial SHA
`09ee0a2afecc2af6c3a216b225537c680ef68848`; the unchanged `main` rollback
baseline is `383efc840832d474cd9d60e0368ed2ded828e03c`.

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
Actions and runner inputs in the evidence workflow, except for the
`aquasecurity/setup-trivy` action handled below.

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

### Commit-pinned setup-trivy action

The first hosted Batch B second cycle reported `no-result` for Renovate's native
`github-tags` lookup of `aquasecurity/setup-trivy`. The dependency is public and
valid: tag `v0.3.1` resolves to the exact checked-in commit
`81e514348e19b6112ce2a7e3ecbafe19c1e1f567`. Adding a broad GitHub credential or
ignoring the dependency would expand access or hide future updates without
fixing the failed lookup path.

`renovate.json` therefore disables only the native `github-actions` record for
this package. A repository-specific regex manager matches the same
commit-pinned workflow line and uses Renovate's `git-tags` datasource against
the public Git repository. Its replacement template updates the tag comment and
40-character commit together, preserving the supply-chain pin. This is a lookup
transport correction, not an ignore rule or a request to change the current
action version.

## Workspace image evidence

`.github/workflows/workspace-image-security-evidence.yml` preserves weekly and
manual operation on `main`, accepts direct runs of the exact trial ref, and runs
for same-repository pull requests targeting `dependency-automation-trial`.
Fork pull requests and pull requests targeting other branches are rejected. The
job uses read-only repository permissions and:

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
4. On `main`, uploads raw build, base-index, package, vulnerability, and scanner
   evidence for seven days even if an earlier step fails. On the trial branch
   and its trusted pull requests, measures the complete sealed evidence bundle
   and retains it for one day only when the trial upload variable is enabled.

Vulnerability findings do not fail the scheduled evidence job. Build,
base-resolution, database-download, inventory, scan, platform, required-package,
or artifact-upload failures do fail it. The image is never pushed, no live
workspace or host credential mount is used, and the built image's entrypoint is
never started.

Trial runs start with schedules, the optional Trivy Actions cache, and uploads
disabled. They still perform the complete no-cache Docker build and scan, then
measure a sealed allowlist containing reports and build logs but not the Docker
image, layers, Trivy database, or dependency caches. After the operator enables
the repository upload variable, the complete final `.tar.gz` payload must be at
most 24 MiB (25,165,824 bytes). The temporary tar size is recorded only as a
measurement and does not determine upload eligibility. The upload action keeps
compression disabled because the payload is already gzip-compressed, and an
exact-ID API check fails the job if GitHub reports a retained artifact above 25
MiB (26,214,400 bytes). Missing allowlisted inputs, unsafe traversal paths,
archive failures, compressed-payload overflow, upload failures, and retained
size overflow all fail closed without trimming `workspace-image-scan`. The
exact schedule, cache, and upload variables are owned by the
[orchestration trial workflow policy](../../orchestration/docs/dependency-automation.md#trial-workflow-controls).
The known hosted measurement—42,276,809 source bytes, a 42,301,440-byte
temporary tar, and a 5,754,918-byte final gzip—is eligible under the payload cap
without changing archive contents; uploads remain disabled until the operator
checkpoint authorizes one.

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

After the hosted `setup-trivy` warning, Renovate 44.65.5 strict configuration
validation passed for the fallback. A credential-free local extraction using
the new manager resolved `v0.3.1` and its exact current commit through public Git
refs with no warning and no available update. Workspace PR #9 then published the
fallback at `110e5f78fd995ed281d425f9da90bc81079f651d`. The automatic corrective
cycle refreshed Dashboard #8 with the exact setup-trivy tag and commit and no
repository problem. Image-evidence run 35098592885 passed at the same revision
with the optional cache and uploads disabled and zero artifacts.

## Phase 12 operator handoff

The following remains pending or requires retained Phase 12 evidence:

- Repository: `budgetanalyzer/workspace`. Check: Batch C representative
  Renovate PR for `mitmproxy` 12.2.3. Action: after the same-repository
  trial-targeted pull-request trigger is published, select only that exact
  Dashboard proposal and leave the resulting PR open and unmerged. Proof:
  retain the expected one-version Dockerfile diff, trial base, no-automerge
  state, and successful no-cache image-evidence workflow with caches and uploads
  disabled and zero artifacts.
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
  Dependabot alert settings. The operator enabled the graph and alerts during
  Batch A while keeping Dependabot version and overlapping security-update PRs
  disabled. Proof: preserve sanitized settings and alert evidence for the final
  cross-repository coverage report.

Renovate and Trivy do not establish lifecycle support. Node, Go, Java, Ubuntu,
Kubernetes, Helm, Kind, and other installed tools remain subject to the
quarterly human upstream-support review owned by the shared policy.
