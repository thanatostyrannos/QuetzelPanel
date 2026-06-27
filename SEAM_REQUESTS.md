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

## WP-D — multi-tenant + multi-cluster enterprise view

### 1. `backend/app/providers/k8s.py` (SHARED — APPLIED by WP-D)

Two changes already applied on the WP-D branch:

**`K8sProvider._to_server`** — now reads `spec.get("customer")` and
`spec.get("maxPlayers")` from the CR and sets them on the returned
`GameServerSpec`.  Without this the `spec.customer` field was always `None`,
breaking tenancy scoping (`scope_for` / `visible_servers`) in live k8s mode.

**`K8sProvider.create_server`** — now copies `opts["customer"]` (string) into
`spec["customer"]` when present, mirroring the existing `maxPlayers` propagation
(WP-B) on the line above.

### 2. Bootstrap admin — wiring into `backend/app/main.py` lifespan (LEAD ACTION REQUIRED)

A new function `bootstrap_admin(user_store)` lives in `backend/app/auth/bootstrap.py`
and is re-exported from `backend/app/users/__init__.py` as `bootstrap_admin`.

The lead must wire it into the `main.py` lifespan, e.g.:

```python
from app.auth.bootstrap import bootstrap_admin
from app.deps import get_user_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_admin(get_user_store())   # idempotent no-op when env vars absent
    # ... rest of startup (JWT verifier, etc.)
    yield
```

Environment variables consumed (set in `quetzel-auth` Secret):
  QUETZEL_BOOTSTRAP_ADMIN_USER      (default: "admin")
  QUETZEL_BOOTSTRAP_ADMIN_PASSWORD  (required; omit = no-op)

### 3. Helm chart — `quetzel-auth` Secret + backend env (LEAD ACTION REQUIRED)

The lead must add two keys to `charts/quetzel/templates/auth-secret.yaml` and
expose them as backend env vars:

In `charts/quetzel/values.yaml` (under `auth:`):
```yaml
auth:
  bootstrapAdmin:
    username: ""    # default: "admin" (handled in bootstrap.py)
    password: ""    # empty = no bootstrap admin created
```

In `charts/quetzel/templates/auth-secret.yaml` (under `data:`):
```yaml
QUETZEL_BOOTSTRAP_ADMIN_USER: {{ .Values.auth.bootstrapAdmin.username | b64enc }}
QUETZEL_BOOTSTRAP_ADMIN_PASSWORD: {{ .Values.auth.bootstrapAdmin.password | b64enc }}
```

In `charts/quetzel/templates/backend.yaml` env section, add (when auth.enabled):
```yaml
- name: QUETZEL_BOOTSTRAP_ADMIN_USER
  valueFrom:
    secretKeyRef:
      name: quetzel-auth
      key: QUETZEL_BOOTSTRAP_ADMIN_USER
- name: QUETZEL_BOOTSTRAP_ADMIN_PASSWORD
  valueFrom:
    secretKeyRef:
      name: quetzel-auth
      key: QUETZEL_BOOTSTRAP_ADMIN_PASSWORD
```

The e2e harness (`e2e/verify.sh`) reads `QZ_ADMIN_USER` / `QZ_ADMIN_PASS` to log
in as the bootstrap admin. Set these to match the chart values at deploy time.

### 4. `operator/quetzel_operator/manifests.py` (SHARED — APPLIED by WP-D)

`labels(name, customer=None)` now accepts an optional `customer` argument.
When set, `quetzel.gg/customer: <customer>` is added to the label map.

`_meta(name, namespace, owner, customer=None)` passes `customer` through.

All builders (`build_secret`, `build_service`, `build_pdb`, `build_statefulset`)
now accept `customer=None` and forward it to `_meta` and `labels`.

The kopf handler (`handlers.py`) extracts `spec.get("customer")` and passes it
to all `_ensure_*` helpers so every child object inherits the label.

### 5. `frontend/src/App.tsx` — Enterprise Dashboard mount (LEAD ACTION REQUIRED)

Import and conditionally render the enterprise dashboard for platform-admins:

```tsx
import { EnterpriseDashboard } from "./components/EnterpriseDashboard";

// Inside the App component, below the header, add a nav toggle visible only
// when user.role === "platform-admin":
const [view, setView] = React.useState<"servers" | "enterprise">("servers");

// In the header area:
{user?.role === "platform-admin" && (
  <div className="flex gap-2 mb-4">
    <button onClick={() => setView("servers")}
      className={view === "servers" ? "underline font-bold" : ""}>
      My Servers
    </button>
    <button onClick={() => setView("enterprise")}
      className={view === "enterprise" ? "underline font-bold" : ""}>
      Enterprise
    </button>
  </div>
)}

// In the main content area:
{view === "enterprise" && user?.role === "platform-admin"
  ? <EnterpriseDashboard />
  : </* existing server list / deploy UI */>
}
```

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
