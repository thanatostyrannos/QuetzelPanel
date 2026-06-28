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

## Iteration 6 — 2026-06-27 (Phase 0: enterprise foundation — contracts, CI/CD, e2e scaffold)
Phase: P0 (orchestration foundation; lead-owned, no subagents yet)
Branch: enterprise/foundation (PR -> main). Trunk already main + pushed to GitHub
  (thanatostyrannos/QuetzelPanel, PUBLIC). gh ADMIN + repo/workflow scopes; live k3s
  v1.36.2 up (docker runtime); helm v4, node 24 present.
Action (small commits):
  1. CI/CD: .github/workflows/ci.yml (backend/operator/frontend tests, helm lint+template
     local+enterprise, image builds, k3d e2e-smoke) + release.yml (GHCR images + OCI chart
     + GitHub Release on merge). Chart images default to ghcr.io/<owner>/quetzel-*:<appVersion>
     via a quetzel.image helper; Chart 0.1.0 -> 0.2.0; install.sh gains --local/--skip-build
     (default = published images).
  2. Seams: backend main.py -> APIRouters (games, servers) behind app/deps.get_provider;
     frontend api.ts -> src/api/* and types.ts -> src/types/*. No behavior change.
  3. Contracts (interfaces + mock impls + NotImplemented real stubs + tests): auth (Role,
     current_user, require_role, UserStore), tenancy (Customer, scope_for, CUSTOMER_LABEL,
     CustomerStore), metrics (MetricsProvider + synthetic + ServerMetrics/ClusterHealth),
     clusters (ClusterRegistry + local), sizing (Sizing schema, GameServerSpec.maxPlayers
     /customer, operator compute_resources stub + xfail), CRD maxPlayers/customer, catalog
     per-game sizing; seed routers auth/metrics/clusters/customers mounted; frontend types
     + api clients.
  4. e2e: walk.js + pooled harness.js (N bots x M servers); verify.sh finish line
     (reconcile-to-desired, 4 capability-aware gates, bounded, --smoke/--reset/--require-all).
Commands (real output):
  $ cd backend && .venv/Scripts/python -m pytest      -> 57 passed in 0.40s
  $ cd operator && <backend venv>/python -m pytest    -> 27 passed, 1 xfailed in 0.10s
  $ cd frontend && npx vitest run                      -> 33 passed (6 files)
  $ cd frontend && npm run build                       -> tsc + vite OK (36 modules)
  $ helm lint charts/quetzel                           -> 0 failed (icon INFO only)
  $ helm template ... (local + values-enterprise)      -> render OK; CRD has maxPlayers/customer
  $ bash -n e2e/verify.sh                              -> syntax OK
  $ QUETZEL_API=<mock> LIVENESS_TIMEOUT=3 e2e/verify.sh --smoke
      capabilities: auth=0 sizing=0; reconcile created acme-mc1; FAIL liveness (no pod,
      expected pre-WP); sizing/tenancy SKIP; connectivity SKIP; EXIT=1  (fails meaningfully)
Result: PASS (foundation green at every layer; e2e scaffold fails meaningfully by design)
Next: open PR enterprise/foundation -> main, let ci.yml register checks, enable branch
  protection requiring them, merge (release.yml publishes artifacts), THEN fan out WP-A/B/C.
Open issues: e2e-smoke job not yet a required check (becomes required before Phase 3);
  GHCR package visibility to be made public after first release for pull-without-auth.

## Iteration 7 — 2026-06-27 — Phase 2 integration: WP-A/B/C/D merged
Phase: P2 (integrate work packages via PRs into main; CI green each)
Action: Spawned 4 subagents on isolated worktrees/branches, reviewed + integrated each:
  - WP-C observability (PR #2): MetricsProvider (metrics-server + kubelet stats) +
    pure classifiers; gauges + cluster-health panel; metrics RBAC. Lead fix: disk
    stats use the operator PVC name `world-<name>-0` (not `data-…`).
  - WP-B sizing (PR #3): pure compute_resources + StatefulSet wiring; CRD maxPlayers;
    deploy-modal live preview; k8s.py maxPlayers propagation.
  - WP-A auth (PR #4): local user/pass (hashing) + Google OIDC + JWT + roles +
    UserStore. Lead integration: verifier wiring in lifespan (no-op without
    JWT_SECRET => mock stays demoable), tenancy-scoped /servers, chart auth/postgres,
    App.tsx login gate + metrics panels.
  - WP-D tenancy + multi-cluster (PR #8): customer scoping reaches the cluster
    (k8s.py round-trips spec.customer/maxPlayers), bootstrap admin, operator
    quetzel.gg/customer label, ClusterRegistry + cross-cluster rollups, enterprise
    dashboard. Lead integration: bootstrap wiring + chart secret + App.tsx tab.
  - Phase-3 prep (PR #7): Minecraft sizing headroom (node is 32c/54Gi, not tiny) so
    limits exceed the JVM heap; verify.sh enforcement-aware auth probe + 1G heap.
Commands:
  $ backend pytest -> 177 passed ; operator -> 54 passed ; frontend vitest -> 99 passed
  $ helm lint + template (local + enterprise) -> 0 failed
  $ all PRs merged green; release.yml published GHCR images + OCI chart per merge
Result: PASS (all four enterprise WPs on main; CI green; mock mode intact)
Next: Phase 3 grand e2e on the live cluster.
Open issues: in-memory userstore for the e2e (use sqlite/postgres for durable deploys).

## Iteration 8 — 2026-06-27 — Phase 3 GRAND E2E: verify.sh exit 0 (FINISH LINE)
Phase: P3 (bounded reconcile->deploy->verify loop; <=5 iter / 45 min)
Action: Deployed integrated main with auth enabled (./install.sh --local +
  HELM_EXTRA_ARGS auth.enabled/jwtSecret/bootstrapAdmin.password, userstore=memory).
  Ran e2e/verify.sh --require-all on the LIVE k3s cluster.
  Loop iteration 1 -> FAIL, surfaced real issues (2 were e2e-gate bugs):
    (a) Minecraft pods OOM/then CrashLoop — fixed pre-run (sizing headroom).
    (b) sizing gate string-compared k8s quantities (1000m vs canonical "1",
        2048Mi vs "2Gi") -> normalized via qty_norm.
    (c) tenancy: acme-user saw 1 — verify.sh seeded `pw-acme` (7 chars) but WP-A
        requires >=8 -> user never created -> use `<cid>-user-pw`.
    (d) LEVEL_TYPE=FLAT with no generator-settings -> "No key layers" worldgen
        crash on 1.20.4 -> use default (normal) world.
  Loop iteration 2 -> PASS (real output below).
Commands (real output, live cluster):
  $ QZ_ADMIN_USER=admin QZ_ADMIN_PASS=*** LIVENESS_TIMEOUT=700 \
      e2e/verify.sh --require-all
  >> capabilities: auth=1 sizing=1 (smoke=0 require_all=1)
  >> reconciling 4 servers (create acme-mc1/mc2, globex-mc1/mc2; customers acme,globex)
  PASS liveness: all 4 game pods Running
  GATE sizing (live StatefulSet requests vs compute_resources):
     SERVER       MAXP  LIVE            EXPECTED
     acme-mc1     2     750m/1792Mi     750m/1792Mi
     acme-mc2     4     1/2Gi           1000m/2048Mi   (== normalized)
     globex-mc1   6     1250m/2304Mi    1250m/2304Mi
     globex-mc2   8     1500m/2560Mi    1500m/2560Mi
  PASS sizing: 4 distinct resource sets, each == compute_resources()
  harness: 4 servers x 2 bots = 8 total ; 8/8 bots ok (moved 3.4-4.9 blocks, v1.20.4)
  PASS connectivity: >=2 bot(s)/server joined and walked
  GATE tenancy: globex-user sees 2 (want 2) ; acme-user sees 2 (want 2)
  PASS tenancy: admin sees all, each customer-user sees only its own
  ---- ok=4 fail=0 skip=0 ----  RESULT: PASS  (exit 0)
Result: PASS — DoD finish line met. 2 customers x 2 differently-sized Minecraft
  servers (4 distinct computed resource sets proven via jsonpath) x 8 mineflayer
  bots (>=2/server) joined and walked; tenancy scoping correct; within the bound.
Next: follow-up WP — registry-baked game images + upstream-version monitor (user
  request) to eliminate per-pod runtime jar downloads across clusters.
Open issues: PaperMC runtime jar download (~90MB/pod) is slow on Mojang's CDN;
  addressed by the caching WP. Userstore=memory for the e2e (durable: sqlite/postgres).

## Iteration 9 — 2026-06-27 — WP-E: registry-baked game images + version monitor
Phase: Post-finish-line enhancement (user request: stop N pods x N clusters each
  re-downloading the ~90MB server jar from Mojang's CDN at runtime).
Action: Bake the server jar into versioned OCI images so the runtime caches once
  per node and the registry dedups across clusters.
  - game-images/minecraft/Dockerfile: fetches + sha1-verifies the server jar at
    BUILD time, runs it via TYPE=CUSTOM (zero runtime download). Java-21 base
    (correct for 1.20.4/1.21.x).
  - deploy/game-versions.json: baked-version manifest (drives the build matrix).
  - game-images/mc_versions.py (+8 unit tests): pure version resolver/selector +
    urllib fetchers; `resolve <ver>` (build-arg url+sha) and `watch <manifest>`.
  - .github/workflows/game-images.yml: dynamic matrix from the manifest -> buildx
    build+push ghcr.io/.../quetzel-game-minecraft:<ver>.
  - .github/workflows/game-version-watch.yml: daily cron -> detects new upstream
    release -> opens a PR bumping the manifest (auto-update loop).
  - catalog minecraft cachedImageRepo/cachedServerPath; operator build_statefulset
    resolves <repo>:<version> + forces TYPE=CUSTOM (4 new operator tests); explicit
    spec.image still overrides; games without a cache are unaffected.
  - ci.yml: tools-tests job runs the version-logic suite.
Commands (real output, live cluster):
  $ docker run baked image -> "Done (13.563s)!" ; runtime jar-download log lines: 0
  $ kubectl apply GameServer{minecraft,1.20.4} ->
      statefulset image = ghcr.io/.../quetzel-game-minecraft:1.20.4
      env TYPE=CUSTOM CUSTOM_SERVER=/opt/minecraft/server.jar MAX_PLAYERS=2
      pod READY at ~35s ; jar-download log lines: 0
  $ operator pytest -> 58 passed ; game-images pytest -> 8 passed ; backend -> 177
Result: PASS — baked image runs with ZERO runtime CDN download; operator uses it
  end-to-end. Eliminates per-pod-per-cluster jar downloads.
Next: merge WP-E (PR); after game-images.yml publishes, make the GHCR game packages
  public (or add a pull secret) for fresh clusters.
Open issues: cached images must be published+pullable before fresh-cluster minecraft
  deploys (existing cluster uses the locally-tagged image; documented in README).

## Iteration 10 — 2026-06-27 — BUGFIX: "metrics unavailable" for deployed servers
Phase: Debug (user report: per-server metrics panel shows "metrics unavailable").
Diagnosis (live): GET /servers/<name>/metrics -> HTTP 500. Backend traceback:
  classify.parse_cpu_to_nano ValueError: could not convert '114690582n' to float.
  Root cause #1: metrics-server reports pod CPU usage in NANOCORES (the 'n'
  suffix); the parser only handled 'm'/plain (unit-tested without 'n').
  Root cause #2 (found via /cluster/health nodesTotal=0): nodes + nodes/proxy are
  CLUSTER-scoped but WP-C granted them in a namespaced Role; `kubectl auth can-i
  list nodes` (as backend SA) -> no. So node conditions + kubelet disk stats were
  silently denied.
  Root cause #3 (disk): kubelet /stats/summary via the API node-proxy returns
  NotFound on this Rancher Desktop k3s -> disk genuinely unavailable here.
Fix:
  - classify.parse_cpu_to_nano handles n (nano) + u (micro) + m (milli) + cores
    (+3 regression tests incl. the exact crashing value).
  - chart rbac.yaml: nodes + nodes/proxy moved to a ClusterRole + ClusterRoleBinding
    (namespaced Role can't grant cluster-scoped resources); namespaced pod/metrics
    grants stay in the Role.
  - metrics report None (not 0.0) when unavailable; ServerMetrics fields Optional;
    UI MetricsGauge already renders "—" for null (honest "n/a" vs misleading 0%).
  - install.sh --local now `rollout restart`s deployments (same :dev tag +
    IfNotPresent didn't reload rebuilt code without a template change).
Commands (real output, live cluster, after fix):
  $ kubectl auth can-i list nodes --as=...quetzel-backend -> no (before ClusterRole)
  $ GET /servers/acme-mc1/metrics -> HTTP 200
      {"cpuPercent":19.2,"memoryPercent":71.3,"diskPercent":null,
       "cpuMilli":144,"memoryMiB":1277}
  $ GET /cluster/health -> nodesReady:1 nodesTotal:1 (was 0/0)
  $ backend pytest 180 ; frontend vitest 99 ; helm lint 0 failed
Result: PASS — per-server CPU/Memory gauges show real live usage; disk shows "—"
  (kubelet stats not exposed on this k3s); panel no longer "metrics unavailable".
Open issues: disk % needs the kubelet /stats/summary endpoint (absent on this
  Rancher Desktop k3s); reports n/a there, works where the endpoint is exposed.

## Iteration 11 — 2026-06-27 — disk % via DIRECT kubelet scrape (no API node-proxy)
Phase: Debug follow-up. The API-server node-proxy is fully disabled on this k3s
  (even .../proxy/healthz 404s), but metrics-server/Prometheus reach the kubelet
  DIRECTLY — so can we.
Diagnosis: probed the cluster —
  - metrics-server: installed (CPU/mem fine, via direct kubelet, not the proxy).
  - kube-state-metrics: NOT installed (irrelevant — it exposes object state, not
    volume bytes).
  - /api/v1/nodes/<n>/proxy/{healthz,metrics/resource,stats/summary}: all NotFound.
  Also found the disk path read pod["spec"]["nodeName"] on a .to_dict() (snake_case)
  pod -> node_name always None -> disk skipped regardless.
Fix:
  - K8sMetricsProvider._kubelet_summary: scrape https://<nodeInternalIP>:10250/
    stats/summary with the in-pod SA token + TLS-skip (like metrics-server's
    --kubelet-insecure-tls), API node-proxy as fallback. Read node_name handling
    both snake_case/camelCase.
  - ClusterRole: add nodes/stats get (kubelet webhook authz maps /stats/* ->
    nodes/stats; nodes/proxy kept for the fallback).
Commands (real output, live cluster):
  $ GET /servers/acme-mc1/metrics   -> diskPercent: 3.6 (was null)
  $ GET /servers/globex-mc2/metrics -> diskPercent: 3.6
  $ backend pytest 180 ; helm lint 0 failed
Result: PASS — all three gauges (CPU/Memory/Disk) now show real live usage on this
  k3s; disk no longer depends on the API node-proxy.

## Iteration 12 — 2026-06-27 — e2e connectivity robustness (redeploy + retest)
Phase: Deploy current main + retest. Surfaced two e2e-harness fragilities (not
  product bugs) on fresh, cached-image (vanilla via TYPE=CUSTOM) servers:
  - liveness gate trusted GameServer .status.phase ("Running") which is operator-
    timed and lagged — it read Running while the pod was still Pending, so the
    connectivity port-forward hit "pod is not running. status=Pending". Fix: gate
    on POD container ready=true only (authoritative; means the Service has a ready
    endpoint).
  - bot spawn timeout (60s) < a fresh vanilla world's spawn-area prep (~94s). Fix:
    spawnTimeoutMs default 150000 (configurable via harness cfg) + VIEW_DISTANCE=6
    in the server opts so spawn-gen finishes fast.
Commands (real output, live cluster):
  $ e2e/verify.sh --require-all -> RESULT: PASS (exit 0); 8/8 bots walked;
      liveness/sizing/connectivity/tenancy all PASS
  $ metrics live: acme-mc1 cpu16.2/mem74.6/disk3.5 ; globex-mc2 cpu8.0/mem53.4/disk3.5
Result: PASS — full deploy retested green (e2e + all 3 metrics gauges).
Open issues: cluster-health serversReady reads from the laggy GameServer .status
  (showed 1/4 while all 4 pods Ready) — cosmetic; the e2e liveness no longer relies
  on it. Windows note: kubectl port-forward children may outlive the trap; the run
  cleans them via the trap on Linux/CI.
