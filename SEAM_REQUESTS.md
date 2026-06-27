# SEAM REQUESTS

Cross-package wiring that WP leads need to apply in lead-owned files.
Each section is owned by the WP that opened it.

---

## WP-A — Authentication (local + Google OIDC, JWT, roles)

### 1. `backend/app/main.py` — wire JWT verifier at startup

Add the following import and lifespan call so the token verifier is installed
when the app starts (and torn down on shutdown so tests can reset):

```python
# At the top of the file, add:
from .auth.jwt import jwt_config_from_env, build_token_verifier
from .auth.context import set_token_verifier
```

Inside the `lifespan` async context manager, **before** `yield`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # WP-A: wire JWT verifier (no-op in mock mode — JWT_SECRET not set)
    cfg = jwt_config_from_env()
    if cfg is not None:
        set_token_verifier(build_token_verifier(cfg))

    provider = get_provider()
    await provider.startup()
    yield
    await provider.shutdown()

    # WP-A: clear verifier on shutdown so tests reset cleanly
    set_token_verifier(None)
```

The verifier is a no-op (permissive ANONYMOUS_ADMIN) when `JWT_SECRET` env var
is absent, keeping `QUETZEL_PROVIDER=mock` fully usable without any env config.

### 2. `backend/app/routers/servers.py` — enforce auth on server routes

Add `Depends(current_user)` to protected endpoints. Import at the top:

```python
from ..auth.context import AuthContext, current_user
```

Then add the dependency to each route that should be protected:

```python
@router.get("", response_model=list[GameServer])
async def list_servers(
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),   # <-- add this
):
    ...

@router.post("", response_model=GameServer, status_code=201)
async def create_server(
    payload: CreateServerRequest,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),   # <-- add this
):
    ...

@router.delete("/{name}", status_code=204)
async def delete_server(
    name: str,
    provider: Provider = Depends(get_provider),
    user: AuthContext = Depends(current_user),   # <-- add this
):
    ...
```

When the JWT verifier is wired (Step 1) and a request arrives without a valid
`Authorization: Bearer <jwt>` header, `current_user` raises HTTP 401. In mock
mode (no verifier) it returns `ANONYMOUS_ADMIN` and everything works as before.

### 3. `charts/quetzel/values.yaml` — add auth + db safe defaults

Append the following to `values.yaml` so `helm lint` passes without overrides
and the local profile stays disabled-by-default:

```yaml
# Auth (WP-A) — disabled by default (mock/dev). Enable in values-enterprise.yaml.
auth:
  enabled: false
  jwtSecret: ""           # REQUIRED when enabled=true; pass at helm install time
  jwtAlgorithm: HS256
  jwtTtl: 3600
  google:
    clientId: ""          # Set at install time; empty = Google OIDC disabled
    clientSecret: ""
    redirectUri: ""       # Defaults to https://<ingress.host>/api/auth/google/callback

# In-cluster Postgres (WP-A) — disabled by default (use InMemory in dev).
# Enable in values-enterprise.yaml; substitute an external DB for real prod.
postgres:
  enabled: false
  image: postgres:16-alpine
  database: quetzel
  username: quetzel
  password: ""            # REQUIRED when enabled=true; pass at helm install time
  storageSize: 10Gi
  storageClass: ""        # Empty = cluster default (local-path in k3s)
```

### 4. `backend/app/main.py` (or `backend.yaml` Helm template) — inject Secret

Once `auth-secret.yaml` is deployed, tell the backend Deployment to consume it.
In `charts/quetzel/templates/backend.yaml`, add to the container env section:

```yaml
{{- if ((.Values.auth).enabled) }}
envFrom:
  - secretRef:
      name: quetzel-auth
{{- if .Values.postgres.enabled }}
  - secretRef:
      name: quetzel-postgres-credentials
{{- end }}
{{- end }}
```

Also add the `QUETZEL_USERSTORE` env var so the backend picks the right store:

```yaml
- name: QUETZEL_USERSTORE
  value: {{ if .Values.postgres.enabled }}"postgres"{{ else if ((.Values.auth).enabled) }}"sqlite"{{ else }}"memory"{{ end }}
```

### 5. `frontend/src/App.tsx` — gate the app behind login + show current user

Import the auth hook and LoginPage from WP-A:

```tsx
import { useAuth } from "./auth/useAuth";
import { LoginPage } from "./components/LoginPage";
```

Inside `App()`, call `useAuth()` and gate the main UI:

```tsx
const { user, isAuthenticated, login, logout, loading } = useAuth();

// Show a spinner while restoring session
if (loading) {
  return (
    <div className="flex min-h-screen items-center justify-center text-white/50">
      Connecting…
    </div>
  );
}

// Show login page if not authenticated
if (!isAuthenticated) {
  return <LoginPage onLogin={login} />;
}
```

Add a logout button + current-user display inside the header's right-side
`<div className="flex items-center gap-3 text-xs">`:

```tsx
{/* Current user + logout — add after the provider badge */}
<span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-white/60">
  {user?.username}
  <span className="ml-1 text-brand-400/60">({user?.role})</span>
</span>
<button
  onClick={logout}
  className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-white/60 hover:text-white/90 transition"
>
  Sign out
</button>
```

### 6. Backend env var reference (QUETZEL_USERSTORE)

The userstore factory in `backend/app/users/__init__.py` and
`backend/app/tenancy/store.py` read `QUETZEL_USERSTORE`:

| Value      | Store                    | When to use                        |
|------------|--------------------------|------------------------------------|
| `memory`   | InMemoryUserStore        | dev/CI/mock (default)              |
| `sqlite`   | SQLiteUserStore          | local profile, single-node         |
| `postgres` | PostgresUserStore (stub) | enterprise (implement WP-D or here)|

`QUETZEL_DB_PATH` sets the SQLite file path (default: `quetzel.db`).
`QUETZEL_DB_DSN`  sets the Postgres DSN (e.g. `postgresql://user:pw@host/db`).
