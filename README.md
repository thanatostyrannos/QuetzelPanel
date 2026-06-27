# QuetzelPanel

One-click **game-server hosting on Kubernetes**. Pick a game in a modern web UI, click
Deploy, and a Kubernetes operator provisions, exposes, and tears down a dedicated server
for it. Built as a single monorepo: a `GameServer` CRD + controller, a REST API, and a
React SPA.

> **Current status (local):** the Rancher Desktop / k3s cluster on this machine won't
> start (WSL distros stay *Stopped*, see [BLOCKERS.md](BLOCKERS.md)). The product is fully
> working **against a mocked Kubernetes layer** so the UI and API run end-to-end today; the
> real operator/CRD/Helm path is written and validated offline and drops in unchanged once
> the cluster is healthy (`QUETZEL_PROVIDER=k8s`).

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
./install.sh                 # build images, install the chart, wait for rollouts, print the URL
PROFILE=prod ./install.sh    # also bootstrap MetalLB/Longhorn/etc (stub for bare metal)
SKIP_BUILD=1 ./install.sh    # reuse existing images
./uninstall.sh               # remove the platform (keeps CRD + GameServers)
PURGE=1 ./uninstall.sh       # remove everything incl. CRD + namespace
```

`install.sh` is idempotent (helm upgrade --install + cached image builds). The platform
installs into the `quetzel` namespace and is exposed via Traefik at
`http://quetzel.localhost/` (or `kubectl -n quetzel port-forward svc/quetzel-frontend 8080:80`).

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
preStop), status derivation, API client, components, and an App deploy→delete flow. k6
exercises read-heavy + create/get/delete churn with latency/error thresholds.

---

## Repo layout

```
backend/      FastAPI app + providers (mock, k8s) + game catalog + pytest
operator/     kopf reconciler + pure manifest/status builders + pytest
frontend/     React + Vite + Tailwind SPA + Vitest
charts/quetzel/  Helm chart (CRD, RBAC, ConfigMap, Deployments, Services, Ingress)
deploy/       exported catalog.json + sample GameServer CRs
k6/           load + smoke tests
install.sh / uninstall.sh / build-images.sh
STATE.md / BLOCKERS.md / STACK.md / CONFIG.md   build log + decisions
```

## Security notes (v1)

- Single trusted user — no auth yet; the slot for it is marked in
  [`backend/app/main.py`](backend/app/main.py).
- RCON passwords are generated and stored in a Secret, never hardcoded or logged.
- Minecraft EULA acceptance is explicit and visible (catalog `EULA=TRUE`, shown in the UI).
- Least-privilege RBAC: the backend can only touch `GameServer` CRs; the operator manages
  only the children it reconciles.
