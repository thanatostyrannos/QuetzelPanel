# Build: Enterprise features for QuetzelPanel — ORCHESTRATED WITH SUBAGENTS

You are the **lead engineer / orchestrator**. The scope is large, so you will decompose it and
delegate well-scoped chunks to **subagents**, then integrate and verify their work. You extend an
EXISTING, working platform — do not rebuild it. Preserve its patterns; keep every existing test green;
ship in small, committed, runnable increments.

---

## 0. What exists today (read before doing anything)
Single git monorepo. Tech is frozen in `STACK.md` — do not change core choices.
- **backend/** — FastAPI. `app/main.py` (routes `GET /games`, `GET/POST /servers`,
  `GET/DELETE /servers/{name}`, `GET /healthz`; has an explicit `# --- AUTH PLACEHOLDER ---`).
  `app/catalog.py` (game catalog = single source of truth). `app/models.py` (pydantic specs).
  `app/providers/` — **Provider interface** (`base.py`) with `mock.py` + `k8s.py`, selected by
  `QUETZEL_PROVIDER=mock|k8s`. Tests: `backend/tests/` (pytest + TestClient). venv: `backend/.venv`.
- **operator/** — `kopf` reconciler. `quetzel_operator/manifests.py` (PURE unit-tested builders),
  `status.py` (pure), `handlers.py` (kopf handlers + status timer), `catalog.py` (loads
  `deploy/catalog.json`). Tests: `operator/tests/`.
- **frontend/** — React + Vite + TS + Tailwind v4. `src/App.tsx`, `api.ts`, `types.ts`,
  `lib/validation.ts`, `components/`. Vitest + RTL. Dev proxies `/api`→`:8000`; prod nginx proxies
  `/api`→`quetzel-backend`.
- **charts/quetzel/** — Helm chart: CRD `gameservers.quetzel.gg/v1alpha1`, least-privilege RBAC
  (separate operator + backend SAs/Roles), catalog ConfigMap, Deployments/Services, Traefik Ingress.
  `values.yaml` has `profile: local|prod`.
- **deploy/**, **k6/**, **e2e/mineflayer/** (a bot that joins a deployed Minecraft server and walks —
  must keep passing), `install.sh`, `uninstall.sh`, `build-images.sh`, `STATE.md`, `README.md`.

## Environment / run & verify
- Rancher Desktop / k3s on Windows+WSL2, **dockerd mode** (`docker build` images are visible to k3s;
  `build-images.sh` auto-detects runtime). `kubectl`/`helm`/`docker` on PATH.
- Fast loop: `QUETZEL_PROVIDER=mock` runs the whole app with no cluster — keep this working.
- Live deploy: `./install.sh` (idempotent). Tests: backend `cd backend && .venv/Scripts/python -m
  pytest`; operator `cd operator && <backend venv>/python -m pytest`; frontend `cd frontend && npm run
  test`; load `tools/k6.exe run k6/*.js`.
- Known gotcha: the kubernetes client `.to_dict()` returns **snake_case** (`load_balancer`, not
  `loadBalancer`) — handle both anywhere you parse API objects.

## Engineering standards (NON-NEGOTIABLE — applies to you AND every subagent)
1. **TDD**: failing test first (red) → implement (green) → refactor. Business logic goes in PURE,
   dependency-free functions (mirror `manifests.py`/`status.py`); I/O (k8s, DB, HTTP, OAuth) in thin
   adapters behind interfaces.
2. **Preserve patterns**: any new cluster/DB/identity concern gets an **interface + a `mock` impl + a
   real impl**, so `QUETZEL_PROVIDER=mock` keeps the whole app demoable/testable offline.
3. **Tests at every layer**: pytest (backend+operator), Vitest/RTL (frontend), extend `k6/` for new
   endpoints. All pre-existing tests stay green. `e2e/mineflayer` must still pass.
4. **Shippable each commit**: small descriptive commits; clean tree; update Helm chart
   (CRD/RBAC/values/templates), `install.sh`, `deploy/catalog.json`, and docs in the same change.
   `helm lint` + `helm template` pass. RBAC stays least-privilege.
5. **Security**: OAuth client secret, JWT key, DB creds → k8s Secrets + Helm values, never hardcoded
   or logged. Authz enforced server-side on every route. Validate all input.
6. **Docs/state**: update `README.md`; append to `STATE.md` each increment (iteration, change, REAL
   command output proving it). Absolute dates.
7. **CI/CD**: every change reaches `main` via a PR whose CI is **green** (all tests + lint +
   `helm lint`/`template` + image builds). Merging a PR to `main` is what produces release artifacts
   (see the CI/CD PIPELINES section). Never merge red; never hand-publish artifacts.

---

## 1. ORCHESTRATION MODEL (how to use subagents)

Subagents start **cold** with no memory of this conversation. So:

### Phase 0 — Contracts & seams (YOU do this directly, sequential, land it first)
This is what makes parallel work safe. Do NOT delegate it.
- **Modularize the seams** so subagents own disjoint files and don't collide:
  - Backend: refactor `app/main.py` to mount domain routers via `APIRouter`
    (`app/routers/{servers,games,auth,metrics,clusters,customers}.py`). main.py only wires routers +
    middleware.
  - Frontend: split `api.ts` into `src/api/{servers,auth,metrics,clusters}.ts` and `types.ts` into
    `src/types/*`; introduce an app shell that lazy-mounts feature areas.
- **Publish the shared contracts** (interfaces + types + mock impls + stubs that throw
  `NotImplemented`), each with a failing test pinning the contract:
  - `UserStore`, `AuthContext`/`current_user` dependency, `Role` enum.
  - `MetricsProvider` (+ synthetic mock).
  - `ClusterRegistry` (+ local-only impl) and cluster-aware provider factory.
  - Tenancy: `Customer` model, `quetzel.gg/customer` ownership label, a pure `scope_for(user)` filter.
  - `compute_resources(sizing, max_players)` signature + catalog `sizing` schema + CRD `maxPlayers`.
  - Frontend shared types: `User`, `Customer`, `ServerMetrics`, `ClusterHealth`.
- **Decide persistence** behind `UserStore`/customer store: Postgres via the chart for `profile:
  enterprise/prod`, SQLite-on-PVC for `profile: local`. Mock impl needs no DB.
- **Stand up CI/CD first** (see the CI/CD PIPELINES section): author `.github/workflows/ci.yml` and
  `.github/workflows/release.yml`, and make the Helm chart's image values point at the published
  registry (overridable for local dev). This must land in Phase 0 so every subsequent WP PR is gated by
  a green CI from day one.
- Land Phase 0 via a PR into `main` (CI green). Now the contracts + pipelines are stable and parallel
  subagents build against them.

### Branching & naming (human-friendly — required)
Trunk is **`main`** on GitHub; all work merges via **pull request** (CI must be green to merge — see
CI/CD PIPELINES). The repo today is local-only on `master`: before starting, rename the trunk to `main`,
push to GitHub, set `main` as the default branch, and enable branch protection that requires the CI
checks. Use readable, kebab-case names everywhere — NO random/auto-generated hashes for branches,
worktrees, or subagent labels.
- Phase 0 lands on `main` via PR first so every work-package branch includes the contracts + pipelines.
- One branch per work package, all cut from `main` after Phase 0, each merged back via its own PR:
  - WP-A → `enterprise/auth`
  - WP-B → `enterprise/player-sizing`
  - WP-C → `enterprise/observability`
  - WP-D → `enterprise/multi-cluster`
- Name each subagent and its worktree to match (e.g. subagent "auth" → worktree `../qz-auth` on branch
  `enterprise/auth`). The label, the worktree dir, and the branch should all read the same.
- Integrate by opening a PR from each `enterprise/*` branch into `main` in dependency order (§1 Phase 2);
  merge only when CI is green, which triggers the release pipeline (artifacts built/published on merge).

### Phase 1 — Fan out to subagents (parallel where independent)
Spawn one subagent per work package below. **Give each subagent an isolated git worktree** (so parallel
edits don't conflict, named per the convention above) and a **self-contained brief** (it has none of
this context). Use the brief
template in §3. Assign **disjoint file ownership** (the matrix in §2) — a subagent must not edit files it
doesn't own; if it needs a change in a shared seam, it returns a request and YOU apply it during
integration.

Dependency order:
- After Phase 0: launch **WP-A (Auth)**, **WP-B (Sizing)**, **WP-C (Observability)** in parallel —
  they're independent given the contracts.
- **WP-D (Multi-tenant + multi-cluster)** depends on WP-A's roles; start its tenancy-scoping once A
  merges, but its `ClusterRegistry`/aggregation half can proceed against the Phase-0 stub in parallel.

### Phase 2 — Integration (YOU, after each subagent returns)
- Open a PR from each `enterprise/*` branch into `main`. Resolve any seam conflicts (you own router
  registration + nav + values.yaml merges). The PR's **CI must pass** (full test suite +
  `helm lint`/`template` + image builds) before merge — do not merge red.
- After merge, confirm the **release pipeline** ran and published the artifacts for that change.
- Then deploy with `./install.sh` and verify on the LIVE cluster (paste real `kubectl`/`curl` output
  into `STATE.md`). Re-run the `e2e/mineflayer` bot — it must still pass.
- 3-strikes rule: if a work package fails CI or live verification 3×, write a `BLOCKERS.md` entry
  (symptom, diagnosis, attempts) and either re-scope the subagent brief or take it over directly.

### Subagent hygiene
- Briefs are self-contained: include the §0 codebase map, §Environment, §Engineering standards, the
  subagent's owned files, its contract(s), and its acceptance criteria. Do NOT assume shared memory.
- Keep subagents narrow: one work package each. If a package is still too big, the subagent may itself
  decompose, but ownership boundaries hold.
- You are responsible for the final integrated result and the Definition of Done.

---

## CI/CD PIPELINES (all artifacts — REQUIRED)

GitHub Actions in `.github/workflows/`. Two pipelines; artifacts are produced **on PR acceptance to
`main`** (i.e. on merge), never from a developer machine.

### `ci.yml` — gate every PR (on `pull_request` to `main`, and pushes to `enterprise/*`)
Must pass before a PR can merge (wire these as required status checks in branch protection). Jobs:
- **backend-tests**: set up Python, `pip install -r backend/requirements.txt`, `pytest` in `backend/`.
- **operator-tests**: `pytest` in `operator/`.
- **frontend-tests**: `npm ci` + `npm run test` + `npm run build` in `frontend/`.
- **helm**: `helm lint charts/quetzel` and `helm template` for both `profile: local` and the
  enterprise/prod profile (fail on render errors).
- **images-build**: `docker build` each of operator/backend/frontend (no push) to prove the Dockerfiles
  build in CI. Use buildx + layer caching.
- (Optional but encouraged) **e2e-smoke**: spin up an ephemeral cluster (e.g. `kind`/`k3d`),
  `helm install`, deploy a GameServer in mock-or-light mode, and assert it reaches Running. Keep it fast.

### `release.yml` — publish artifacts (on `push` to `main`, i.e. after a PR merges; also on tags `v*`)
`permissions: { contents: write, packages: write }`. Jobs:
- **images**: build and **push all three images** to GHCR — `ghcr.io/<owner>/quetzel-operator`,
  `…/quetzel-backend`, `…/quetzel-frontend` — each tagged with the commit SHA, `latest`, and (on a
  `v*` tag) the semver. Multi-arch (amd64+arm64) via buildx if feasible. Log in with `GITHUB_TOKEN`.
- **chart**: `helm package charts/quetzel` and publish it — push the OCI chart to
  `ghcr.io/<owner>/charts/quetzel` (`helm push`) AND attach the `.tgz` to a GitHub Release. The chart's
  default image values must reference the published GHCR images at the matching version.
- **release**: create/update a GitHub Release for the version with the chart `.tgz` and a note listing
  the image digests.

### Versioning & wiring
- Single source of version: `charts/quetzel/Chart.yaml` `version`/`appVersion`; images share that tag
  (plus SHA). A `v<version>` git tag cuts an immutable release.
- `values.yaml` images default to the GHCR refs + chart `appVersion`; `build-images.sh` + `install.sh`
  still support local `quetzel/*:dev` for offline dev (document both; `install.sh --local` or an env
  flag selects local images).
- Keep secrets out of CI logs; use `GITHUB_TOKEN`/repo secrets only. Pin action versions.

### Acceptance
- A PR with a failing test cannot be merged (CI red). A green PR merged to `main` results in all three
  images + the chart published to GHCR and a GitHub Release, with no manual steps. `install.sh` can
  deploy straight from the published artifacts.

---

## 2. FILE-OWNERSHIP MATRIX (prevents collisions)
- **WP-A Auth**: `backend/app/routers/auth.py`, `app/auth/**`, `app/users/**`; `frontend/src/auth/**`,
  `src/components/Login*`, `src/api/auth.ts`; chart: auth Secret + DB templates, `values.yaml` auth/db
  keys (hand merges to lead). Tests alongside.
- **WP-B Sizing**: `backend/app/catalog.py`, `app/models.py` (sizing/maxPlayers fields),
  `operator/quetzel_operator/manifests.py` (`compute_resources` + statefulset wiring), CRD template
  (`maxPlayers`), `deploy/catalog.json` regen; `frontend/src/components/DeployModal.tsx`,
  `src/types/*`. Tests alongside.
- **WP-C Observability**: `backend/app/routers/metrics.py`, `app/metrics/**` (MetricsProvider impls,
  pure parsers/classifiers); chart `rbac.yaml` metrics grants (hand merge to lead);
  `frontend/src/components/Metrics*`, `ClusterHealth*`, `src/api/metrics.ts`. Tests alongside.
- **WP-D Tenancy+Multi-cluster**: `backend/app/routers/{clusters,customers}.py`, `app/tenancy/**`,
  `app/clusters/**` (ClusterRegistry, cluster-aware provider factory); `frontend/src/components/
  Enterprise*`, cluster switcher, `src/api/clusters.ts`. Tests alongside.
- **Lead-owned seams (no subagent edits)**: `backend/app/main.py` (router registration + auth
  middleware), `frontend/src/App.tsx` (nav/shell), `charts/quetzel/values.yaml` merges,
  `.github/workflows/**` (CI/CD), `install.sh`, `README.md`, `STATE.md`. (A WP that needs a new CI step
  — e.g. a DB service for tests — returns the request; the lead edits the workflow.)

---

## 3. SUBAGENT BRIEF TEMPLATE (fill one per work package)
```
You are a senior engineer on QuetzelPanel (Python FastAPI + kopf, React/Vite/TS/Tailwind, Helm/k3s).
You start with NO prior context. Read STACK.md and these files: <list the package's owned files + the
contracts it implements>. 

CONTEXT: <paste §0 codebase map + §Environment + §Engineering standards verbatim>.

YOUR PACKAGE: <epic summary>. 
OWNED FILES (edit only these): <from §2>. If you need a change outside them, STOP and return the exact
request; do not edit shared seams.
CONTRACTS YOU IMPLEMENT: <interface signatures from Phase 0>. Provide a mock impl so QUETZEL_PROVIDER=
mock works, plus the real impl.
TDD: write failing tests first, then implement, then refactor. Add pytest/Vitest tests for everything;
keep all existing tests green.
ACCEPTANCE: <epic acceptance criteria>. 
DELIVERABLE: work on your assigned human-friendly branch (e.g. `enterprise/auth`) in your worktree;
small commits, all tests green; plus a short note of any seam changes the lead must apply.
```

---

## 4. WORK PACKAGES (epics)

### WP-A — Authentication (custom + Google)
Local username/password (argon2/bcrypt) **and** Google OIDC (e.g. Authlib). Signed sessions (PyJWT or
signed HTTP-only cookie). Protect all `/servers`, `/metrics`, `/clusters`, `/customers`, admin routes
via a FastAPI auth dependency at the AUTH PLACEHOLDER. Roles ≥ `platform-admin`, `customer-admin`,
`customer-user`; authz enforced server-side; users belong to a Customer. `UserStore` interface (mock =
in-memory; real = Postgres for enterprise / SQLite for local). Frontend: login page + "Sign in with
Google" + local form, token storage, fetch auth header, route guards, logout, current-user display.
Secrets via Helm → k8s Secret (`googleClientId/Secret`, `jwtSigningKey`, DB creds).
**Acceptance**: unauth API → 401; both login methods yield working sessions; customer-user sees only
their customer's data; tests cover token issue/verify, hashing, guards, role enforcement.

### WP-B — Player-based game sizing
Catalog gains per-game `sizing { baseMemoryMiB, memoryPerPlayerMiB, baseCpuMilli, cpuPerPlayerMilli,
maxPlayers, ceilingMemoryMiB?, ceilingCpuMilli? }`. CRD/spec gains `maxPlayers`. PURE
`compute_resources(sizing, maxPlayers) -> {requests, limits}` (clamped, monotonic, sane rounding),
used by `build_statefulset` when explicit resources are absent (explicit still overrides). Propagate
player count to the game where relevant (e.g. Minecraft `MAX_PLAYERS`). Frontend deploy modal: a
max-players control showing computed CPU/memory live.
**Acceptance**: N players → StatefulSet requests/limits match the formula; unit tests pin the math
(boundaries/clamping); UI preview matches backend.

### WP-C — Observability (per-server usage + cluster health)
Per-server **memory %, CPU %, disk %**: CPU/mem from metrics-server (`metrics.k8s.io/v1beta1` pods) as
% of the pod limits; disk % from PVC volume stats (kubelet summary stats `usedBytes/capacityBytes`).
Behind a `MetricsProvider` (mock = synthetic; k8s = real). Endpoint `GET /servers/{name}/metrics`.
Cluster health: replication (desired vs ready), pods in error/CrashLoopBackOff, node conditions →
`GET /cluster/health`; keep classification PURE + unit-tested. Minimal RBAC additions (`metrics.k8s.io`
pods get/list; `nodes/stats` or `nodes/proxy` get). Frontend: usage gauges per server + cluster-health
panel, polled like the server list.
**Acceptance**: gauges reflect real live usage; a deliberately broken pod shows as Error/CrashLoop;
pure parsers/classifiers unit-tested; mock mode renders plausible data with no cluster.

### WP-D — Multi-tenant + multi-cluster enterprise view
Tenancy: `Customer` entity; every GameServer owned by a customer (spec + `quetzel.gg/customer` label);
listing scoped by caller (admin sees all). Multi-cluster: `ClusterRegistry` = local in-cluster + remote
clusters via stored kubeconfig/SA-token Secrets; provider + metrics provider become cluster-aware (one
client per cluster). Aggregation: `GET /clusters`, `GET /clusters/{id}/health`, `GET /customers`,
`GET /customers/{id}/servers` (cross-cluster rollups for admins). Build in phases: (a) single-cluster
multi-tenant scoping first; (b) cluster registry + cross-cluster aggregation. Frontend: enterprise
dashboard with cluster switcher, customer list, cross-cluster rollups, drill-down; role-appropriate.
**Acceptance**: customer-user sees only their games; admin sees all customers across all registered
clusters; aggregation merges per-cluster data correctly; tenancy filters + registry logic unit-tested;
a second (or mock-remote) cluster appears in the rollup.

---

## 5. DEFINITION OF DONE (whole job)
- All four work packages integrated **via PRs to `main` with green CI**; **all pre-existing tests pass**;
  `e2e/mineflayer` still joins a deployed Minecraft server and walks.
- `QUETZEL_PROVIDER=mock` runs the full feature set with no cluster.
- `helm lint` + `helm template` clean (local + enterprise/prod profiles); RBAC least-privilege;
  `./install.sh` idempotent; deployed and verified on the live k3s cluster with pasted real output.
- **CI/CD live**: PRs are gated by `ci.yml`; merging to `main` publishes all artifacts (operator,
  backend, frontend images + Helm chart) to GHCR with a GitHub Release, no manual steps; `install.sh`
  can deploy from the published artifacts.
- `README.md` updated (incl. how to consume the published images/chart); `STATE.md` logs each iteration
  with real command output; small clean commits.

Start with Phase 0: read `STACK.md`, `backend/app/providers/`, `operator/quetzel_operator/manifests.py`,
`charts/quetzel/`; rename trunk to `main` + push to GitHub with branch protection; author the CI/CD
workflows; modularize the seams; publish the contracts with failing tests; land it via a green PR; THEN
spawn the WP-A/B/C subagents.
