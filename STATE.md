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
