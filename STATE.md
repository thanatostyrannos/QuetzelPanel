# STATE — QuetzelPanel build log

> NOTE: User-directed deviation from the original prompt's "no mocks" rule.
> The k3s cluster will not come up (see BLOCKERS.md B1). On user instruction we
> **mocked the Kubernetes layer** behind the backend's Provider interface and
> built the frontend end-to-end against it. The real `K8sProvider` + operator +
> CRD + Helm chart remain the target; flip `QUETZEL_PROVIDER=k8s` once WSL is fixed.

---

## Iteration 0 — 2026-06-26 ~23:20
Phase: P0 (Env)
Action: Verified environment / attempted to bring up the cluster.
Commands:
  $ kubectl get nodes -o wide
  Unable to connect to the server: dial tcp 127.0.0.1:6443: actively refused
  $ wsl -l -v
  Ubuntu / rancher-desktop / rancher-desktop-data → all STOPPED
  $ rdctl start --path "...Rancher Desktop.exe" --kubernetes.enabled --application.start-in-background
  → GUI processes spawn, distros stay Stopped, :6443 never binds (polled ~4 min)
Result: FAIL (acceptance check: P0 nginx LoadBalancer smoke) — cluster unavailable.
Next: Per user direction, pivot to mock kube layer + frontend.
Open issues: B1 (k3s/WSL won't start).

## Iteration 1 — 2026-06-26 ~23:35
Phase: P3-equiv (Backend API over mock provider)
Action: Froze STACK (Python kopf/FastAPI + React/Vite/TS/Tailwind). Built backend:
  catalog (4 games), pydantic models mirroring the CRD, Provider interface with
  MockProvider (time-driven Pending→Provisioning→Running) and a real K8sProvider
  (CR CRUD, lazy k8s import) selectable via QUETZEL_PROVIDER. FastAPI routes
  /games /servers (CRUD) /healthz. venv + uvicorn on :8000.
Commands:
  $ curl /healthz → {"status":"ok","provider":"MockProvider"}
  $ curl /games  → minecraft, valheim, terraria, factorio
  $ POST /servers {name:mc-demo, game:minecraft, version:1.21.1} → 201
  $ poll /servers/mc-demo:
      t=0s  Pending
      t=2s  Provisioning
      t=7s  Running   addr=192.168.127.2:25565  ready=True
  $ DELETE /servers/mc-demo → 204 ; GET → 404
Result: PASS (acceptance check: API create→Running→delete lifecycle)
Next: Build frontend SPA against the API.
Open issues: B1.

## Iteration 2 — 2026-06-27 ~00:00
Phase: P4-equiv (Frontend end-to-end over mock)
Action: Built React+Vite+TS+Tailwind SPA: branded header w/ live API + provider
  badge, 4-card Game Library grid (gradient art + emoji), Deploy modal (name
  validation, version/storage, explicit EULA notice, RCON-Secret note), My Servers
  list w/ animated status pills, copyable connect address, Delete. 2s polling.
  Vite dev-proxy /api→:8000. Added vite-env.d.ts. Verified via Claude Preview.
Commands (driven in real browser preview, serverId 2120d03f):
  $ GET / → 200 ; GET /api/games (via proxy) → 4 games ; /api/healthz → ok
  $ UI: click Minecraft Deploy → modal → name=mc-survival → Deploy server
       → My Servers shows mc-survival, "Server is live", Running,
         addr 192.168.127.2:25565   (1 total · 1 running)
  $ UI: Delete → "0 total · 0 running", empty state
  $ console (warn+error): No console logs
  $ npm run build → tsc + vite build OK (32 modules, 156 kB / 50 kB gzip)
Result: PASS (acceptance check: UI deploy→Running w/ address→delete, cluster-equiv=mock)
Next: Persist mock state option; then real cluster: operator + CRD + Helm + install.sh
      once B1 (WSL/k3s) resolved. Optionally containerize (Dockerfiles + nginx) for parity.
Open issues: B1 (cluster down); persistence is in-memory (resets on backend restart).

## Iteration 3 — 2026-06-27 ~00:15
Phase: Testing (user-directed) + backend operator logic (no deploy)
Action: Added three test layers (TDD for new code) + the operator reconciler.
  - backend pytest: catalog, models (name validation), MockProvider lifecycle
    (injectable clock — small testability refactor), API CRUD via TestClient.
  - operator (TDD, tests written first → red → green): manifests.py pure builders
    (StatefulSet/Service/Secret, RCON-via-Secret, readiness probe, graceful
    preStop, PVC, owner refs) and status.py (service_address, compute_phase).
  - operator handlers.py (kopf reconciler) written + byte-compiled; NOT run (no
    cluster). catalog.py loader reads deploy/catalog.json (exported from backend).
  - frontend Vitest+RTL: validation (TDD-extracted lib/validation.ts), api client,
    StatusPill, DeployModal, App deploy→delete integration.
  - k6: smoke.js + api_load.js (browse + lifecycle scenarios, thresholds).
Commands:
  $ backend  pytest         → 35 passed
  $ operator pytest         → 24 passed (17 manifests + 7 status)
  $ frontend npm run test   → 30 passed (5 files)
  $ frontend npm run build  → tsc + vite OK (33 modules)
  $ k6 run k6/smoke.js      → checks 100%, http_req_failed 0%
  $ k6 run k6/api_load.js   → 100,125 reqs, 0 failed, 144,833 checks 100%,
                              http_req_duration p95=9.64ms, create p95=8.32ms,
                              ~3,337 req/s — ALL thresholds passed
Result: PASS (89 unit/integration tests green; k6 load green)
Next: When B1 resolved — build images (nerdctl k8s.io), apply CRD+RBAC, run
      operator, then exercise P1–P6 + DoD on the live cluster. Helm chart +
      install.sh/uninstall.sh still to write.
Open issues: B1 (cluster down); operator handlers.py unverified against a live API.

## Iteration 4 — 2026-06-27 ~00:40
Phase: Packaging (user-directed) — Helm chart, CRD, RBAC, Dockerfiles, installers
Action: Wrote the full platform packaging (validated offline; not deployed, B1):
  - charts/quetzel Helm chart: CRD (status subresource + printer cols + OpenAPI
    schema), operator/backend SAs + least-privilege Roles/RoleBindings, catalog
    ConfigMap (embeds files/catalog.json exported from backend), operator/backend/
    frontend Deployments, backend+frontend Services, Traefik Ingress, NOTES.txt.
  - Dockerfiles: backend (uvicorn), operator (kopf), frontend (node build -> nginx
    + baked nginx.conf proxying /api -> quetzel-backend). .dockerignore.
  - install.sh (idempotent: prereqs, cluster/k3s detect, catalog export, image
    build, helm upgrade --install, rollout waits, prints URL; PROFILE=prod stub),
    uninstall.sh (PURGE opt), build-images.sh (nerdctl k8s.io / docker fallback).
  - Added P5 PodDisruptionBudget builder to operator (TDD) + wired into reconciler.
  - README.md (reproducible run instructions), .gitattributes (LF for *.sh).
Commands:
  $ operator pytest                 → 25 passed (added PDB test)
  $ helm lint charts/quetzel        → 0 failed (only icon-recommended INFO)
  $ helm template ... (local+prod)  → 14 docs each, parsed OK by yaml
      objects: CRD, 2 SA, 2 Role, 2 RoleBinding, ConfigMap, 3 Deployment,
               2 Service, Ingress
      catalog ConfigMap embeds valid JSON (4 games)
      operator cmd: kopf run --standalone --namespace quetzel -m quetzel_operator.handlers
      CRD gameservers.quetzel.gg Namespaced, status subresource: True
      backend env: QUETZEL_PROVIDER=k8s, QUETZEL_NAMESPACE=quetzel
Result: PASS (acceptance check: chart lints + renders valid manifests, both profiles)
Next: Resolve B1, then ./install.sh on the live cluster and run DoD P0–P6.
Open issues: B1 (cluster down) — install.sh/build-images.sh/handlers.py not yet
      exercised against a real cluster (offline-validated only).

## Iteration 5 — 2026-06-27 ~07:30  *** B1 RESOLVED — LIVE CLUSTER ***
Phase: P0–P4 on the live cluster + mineflayer agent (user-directed goal)
Context: Rancher Desktop back up. k3s v1.36.2, node Ready, local-path default,
  node IP 192.168.127.2. Runtime is docker://29.1.3 (DOCKERD mode, not containerd)
  -> docker-built images are visible to k3s; updated build-images.sh to detect the
  node runtime and pick docker vs nerdctl accordingly.
Action: Built 3 images (docker), ./install.sh, deployed Minecraft via the API,
  ran a mineflayer bot. Found + fixed TWO real bugs only a live deploy surfaces:
   BUG1: operator CrashLoop 'No module named quetzel_operator' — kopf console
         script doesn't add cwd to sys.path. Fix: PYTHONPATH=/app (chart env +
         Dockerfile).
   BUG2: GameServer stuck Provisioning despite ready pod — service_address read
         camelCase 'loadBalancer' but the k8s client .to_dict() returns snake_case
         'load_balancer'. Fix: accept both + regression test (operator now 26).
Commands (real output):
  $ ./install.sh (SKIP_BUILD=1) → 3 deployments rolled out; printed URL
  $ POST /servers mc-bot (provider=K8sProvider) → CR created, phase Pending
  $ operator logs → created secret/service/statefulset/pdb; reconcile succeeded
  $ kubectl get gs mc-bot → Running, ADDRESS 192.168.127.2:25565, READY true
  $ kubectl get svc mc-bot → LoadBalancer EXTERNAL-IP 192.168.127.2, 25565+25575
  $ minecraft logs → Done (7.614s)! ; RCON running on 0.0.0.0:25575
  $ node e2e/mineflayer/bot.js (port-forward 25565):
       SPAWNED server version=1.20.4 ; players=QuetzelBot
       start (7.5,-60,0.5) -> end (30.2,-60,56.0) ; walked 59.95 blocks
       PASS: bot joined and walked around the deployed server.
Result: PASS — DoD #1 (install), #3 (deploy->Running+address), #4 (connect: a
  mineflayer agent joined and walked ~60 blocks). Real game pod from the operator.
Next: remaining DoD — #2 verify UI on cluster, #5 delete via UI/API + GC, #6 second
  game (Valheim), #7 pod-kill self-heal + PVC persistence, #8 uninstall.
Open issues: kopf cluster-discovery warnings are benign (namespaced watch works).
