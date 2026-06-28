# QuetzelPanel

One-click **game-server hosting on Kubernetes**. Pick a game in a modern web UI, click
Deploy, and a Kubernetes operator provisions, exposes, and tears down a dedicated server
for it. Built as a single monorepo: a `GameServer` CRD + controller, a REST API, and a
React SPA.

> **Status:** runs live on k3s (verified) **and** fully offline against a mocked
> Kubernetes layer (`QUETZEL_PROVIDER=mock`). The **enterprise feature set is merged**:
> CI/CD pipelines + modular routers (foundation), **authentication** (local user/pass +
> Google OIDC, JWT, roles), **player-based sizing**, **observability** (per-server usage +
> cluster health), and **multi-tenant / multi-cluster** (customer scoping + cross-cluster
> rollups) — each shipped via its own PR. The grand e2e (`e2e/verify.sh`) is the finish
> line. See [STATE.md](STATE.md).

---

## Architecture

```
            ┌──────────────┐   REST/JSON   ┌──────────────┐   GameServer CRs   ┌───────────────┐
   browser → │  Frontend    │ ───────────→  │  Backend API │ ───────────────→   │  Operator      │
            │ React+Vite   │   /api/*      │  FastAPI     │                    │  (kopf)        │
            │ (nginx)      │ ←───────────  │              │ ←── status ──────  │                │
            └──────────────┘               └──────────────┘                    └───────┬────────┘
                                                                                        │ reconciles
                                                          StatefulSet + Service(LB) + Secret + PDB
                                                                                        ▼
                                                                               dedicated game pod
```

- **`GameServer` CRD** (`quetzel.gg/v1alpha1`) — spec: `game`, `version`, `image?`,
  `resources`, `storageSize`, `env`, `rconEnabled`; status: `phase`, `address`, `podName`,
  `ready`, `message` (status subresource + printer columns).
- **Operator** (Python + [kopf](https://kopf.readthedocs.io)) reconciles each `GameServer`
  to a **StatefulSet** (`replicas:1` + `volumeClaimTemplate`), a **LoadBalancer Service**,
  a generated-password **Secret** (RCON), and a **PodDisruptionBudget**. Owner references
  garbage-collect children on delete. Readiness probe gates `Running`; a preStop hook does a
  graceful save+stop.
- **Backend** (Python + FastAPI) — `GET /games`, `GET/POST /servers`, `GET/DELETE
  /servers/{name}`, `GET /healthz`. Talks to a **Provider**: `mock` (in-memory) or `k8s`
  (creates CRs). Least-privilege RBAC.
- **Frontend** (React + Vite + TypeScript + Tailwind) — game-card grid, deploy modal,
  My Servers view with live status + connect address.
- **Game catalog** — declarative map in [`backend/app/catalog.py`](backend/app/catalog.py)
  (Minecraft, Valheim, Terraria, Factorio). Adding a game is a catalog entry, no code change.

See [STACK.md](STACK.md) and [CONFIG.md](CONFIG.md) for the frozen tech choices and profiles.

---

## Run it now (mock layer — no cluster needed)

Two processes; needs Python 3.12 and Node 24.

```bash
# backend (terminal 1)
cd backend
python -m venv .venv && . .venv/Scripts/activate    # or: source .venv/bin/activate
pip install -r requirements.txt
QUETZEL_PROVIDER=mock uvicorn app.main:app --port 8000

# frontend (terminal 2)
cd frontend
npm install
npm run dev        # http://localhost:5173  (proxies /api -> :8000)
```

Open http://localhost:5173, pick Minecraft, Deploy, watch it go Pending → Provisioning →
Running with a connect address, then Delete.

---

## Run it on Kubernetes (Rancher Desktop / k3s)

Requires a **running** cluster, `kubectl`, `helm`, and a container engine (`nerdctl`
preferred so images land in the k3s containerd store).

```bash
./install.sh                 # deploy the PUBLISHED GHCR images (chart appVersion)
./install.sh --local         # build local quetzel/*:dev images and deploy those
./install.sh --local --skip-build   # reuse already-built local images
PROFILE=prod ./install.sh    # also bootstrap MetalLB/Longhorn/etc (stub for bare metal)
./uninstall.sh               # remove the platform (keeps CRD + GameServers)
PURGE=1 ./uninstall.sh       # remove everything incl. CRD + namespace
```

`install.sh` is idempotent (helm upgrade --install + cached image builds). The platform
installs into the `quetzel` namespace and is exposed via Traefik at
`http://quetzel.localhost/` (or `kubectl -n quetzel port-forward svc/quetzel-frontend 8080:80`).

### Consume the published artifacts

Merges to `main` publish three images and the Helm chart to GHCR (see CI/CD below):

```bash
# images: ghcr.io/thanatostyrannos/quetzel-{operator,backend,frontend}:<appVersion>
helm install quetzel oci://ghcr.io/thanatostyrannos/charts/quetzel --version <appVersion> \
  --namespace quetzel --create-namespace
```

The chart's default image values already point at those GHCR refs at the matching
`appVersion`; `./install.sh --local` overrides them with local builds for offline dev.

Deploy a server straight from the CLI:

```bash
kubectl apply -f deploy/samples/minecraft.yaml
kubectl -n quetzel get gameservers -w
```

---

## Tests

```bash
# backend unit + API integration (pytest + TestClient)
cd backend && .venv/Scripts/python -m pytest

# operator manifest/status builders (pytest, written test-first / TDD)
cd operator && <backend-venv>/python -m pytest

# frontend unit + integration (Vitest + React Testing Library)
cd frontend && npm run test

# k6 load tests (backend running on :8000)
k6 run k6/smoke.js
k6 run k6/api_load.js
```

Coverage: catalog, model validation, mock-provider lifecycle, full API CRUD, operator
manifest builders (StatefulSet/Service/Secret/PDB, RCON-via-Secret, readiness, graceful
preStop), status derivation, API client, components, and an App deploy→delete flow, plus
the enterprise contracts (roles/auth dependency, UserStore, tenancy scoping, metrics +
cluster registry, sizing schema). k6 exercises read-heavy + create/get/delete churn.

---

## Grand E2E — the finish line

[`e2e/verify.sh`](e2e/verify.sh) is the machine-checkable finish line: it reconciles a
desired set of customers + differently-sized Minecraft servers, then asserts four hard
gates — **sizing** reached the cluster (live StatefulSet resources == `compute_resources`),
**liveness** (all pods Running within a bounded timeout; Pending/CrashLoop ⇒ FAIL),
**connectivity** (≥2 mineflayer bots per server join and walk), and **tenancy** (a
customer-user sees only its own servers; an admin sees all).

```bash
./e2e/verify.sh            # full: 2 customers x 2 servers x >=2 bots (live cluster)
./e2e/verify.sh --smoke    # CI/k3d: 1 customer x 1 server x 1 bot, smallest tier
./e2e/verify.sh --reset    # delete the e2e servers (clean slate)
```

It is idempotent (reuse-or-create by name) and capability-aware: gates whose feature
isn't merged yet print `SKIP` (so the script runs from the foundation through to the full
finish line). The pooled bot harness is [`e2e/mineflayer/harness.js`](e2e/mineflayer/harness.js).

---

## CI/CD

GitHub Actions in [`.github/workflows`](.github/workflows):

- **`ci.yml`** gates every PR to `main` (and `enterprise/*` pushes): backend/operator/
  frontend tests, `helm lint` + `helm template` (local + enterprise profiles), image
  builds, and a k3d **e2e-smoke** (the 1×1×1 form of `verify.sh`).
- **`release.yml`** runs on merge to `main` (and `v*` tags): builds and pushes the three
  images to GHCR, packages + pushes the OCI Helm chart, and cuts a GitHub Release with the
  image digests. `Chart.yaml` `appVersion` is the single source of the version.
- **`game-images.yml`** bakes per-version game-server images (`ghcr.io/<owner>/quetzel-game-minecraft:<ver>`)
  from [`deploy/game-versions.json`](deploy/game-versions.json) — the server jar is fetched at
  **build** time and baked in, so pods never download from Mojang at startup (the runtime caches
  the image once per node; the registry dedups it across clusters). **`game-version-watch.yml`**
  is a daily cron that detects new upstream Minecraft releases and opens a PR adding them — merging
  that PR triggers a fresh bake. The operator uses the cached image for any version the catalog's
  `cachedImageRepo` covers (`TYPE=CUSTOM`), falling back to the runtime-download image otherwise.

Artifacts are produced only on acceptance to `main` — never from a developer machine. (GHCR
packages are private by default; make `quetzel-*` + `quetzel-game-*` public, or configure an
image-pull secret, for clusters to pull them without auth.)

---

## Repo layout

```
backend/      FastAPI app + providers (mock, k8s) + game catalog + pytest
operator/     kopf reconciler + pure manifest/status builders + pytest
frontend/     React + Vite + Tailwind SPA + Vitest
charts/quetzel/  Helm chart (CRD, RBAC, ConfigMap, Deployments, Services, Ingress)
deploy/       exported catalog.json + sample GameServer CRs
e2e/          verify.sh finish-line + mineflayer pooled bot harness
k6/           load + smoke tests
.github/workflows/   ci.yml (PR gate) + release.yml (GHCR images + chart on merge)
install.sh / uninstall.sh / build-images.sh
STATE.md / BLOCKERS.md / STACK.md / CONFIG.md   build log + decisions
```

## Security notes

- **Auth** (local user/pass with hashing + Google OIDC, JWT sessions, roles): the
  `current_user` dependency + `Role` precedence + `UserStore` (`backend/app/auth`,
  `backend/app/users`). In mock/dev with no `JWT_SECRET` configured the verifier is a
  no-op and the app stays demoable (permissive platform-admin); setting `auth.enabled=true`
  + a JWT secret turns enforcement on (unauth `/servers` → 401). A bootstrap admin can be
  seeded from env (`auth.bootstrapAdmin`). OAuth/JWT/DB secrets come from k8s Secrets +
  Helm values. Every server is owned by a `Customer`; listings are tenancy-scoped.
- RCON passwords are generated and stored in a Secret, never hardcoded or logged.
- Minecraft EULA acceptance is explicit and visible (catalog `EULA=TRUE`, shown in the UI).
- Least-privilege RBAC: the backend can only touch `GameServer` CRs; the operator manages
  only the children it reconciles.
