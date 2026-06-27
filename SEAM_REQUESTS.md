# SEAM_REQUESTS — cross-work-package seam edits

This file documents changes WPs need in lead-owned or shared files. The lead
applies/reviews these during integration. (Consumed and removed once all WPs land.)

---

## WP-B — player-based game sizing

### `backend/app/providers/k8s.py`
In `K8sProvider.create_server`, after building `spec`, if `opts.get("maxPlayers")`
is not None, cast to int and add it as `spec["maxPlayers"]` (mirrors MockProvider).
Without this, `maxPlayers` was dropped and the operator could not compute
player-based resources. **Applied by WP-B on its branch (shared file).**

### `operator/quetzel_operator/handlers.py`
No change required — the kopf handler already passes the full spec into
`build_statefulset`, so `spec.maxPlayers` flows through.

---

## WP-C — observability

### 1. `frontend/src/App.tsx` — surface MetricsPanel + ClusterHealthPanel
- `import { MetricsPanel } from "./components/MetricsPanel";`
- `import { ClusterHealthPanel } from "./components/ClusterHealthPanel";`
- Render `<MetricsPanel serverName={s.name} />` inside the servers map, and a
  `<ClusterHealthPanel />` section near "My Servers". (Lead shell pass.)

### 2. `charts/quetzel/values.yaml` — optional `metrics.enabled` toggle (nice-to-have)
Current unconditional RBAC is safe; toggle is optional.

---

## WP-A — authentication

1. **`backend/app/main.py` lifespan** — `jwt_config_from_env()` +
   `set_token_verifier(build_token_verifier(cfg))` before yield; clear after.
   (No-op verifier when `JWT_SECRET` absent → mock/dev stays permissive.)
2. **`backend/app/routers/servers.py`** — add `user: AuthContext = Depends(current_user)`
   to list/create/delete endpoints.
3. **`charts/quetzel/values.yaml`** — add `auth:` (enabled/jwtSecret/google…) and
   `postgres:` (enabled/password…) stanzas with safe `false`/`""` defaults.
4. **`charts/quetzel/templates/backend.yaml`** — `envFrom` the `quetzel-auth` and
   `quetzel-postgres-credentials` secrets when enabled; set `QUETZEL_USERSTORE`.
5. **`frontend/src/App.tsx`** — gate the app behind `useAuth().isAuthenticated`
   (LoginPage), add user badge + logout to the header.
