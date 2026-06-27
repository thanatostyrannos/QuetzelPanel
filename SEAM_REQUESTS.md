# Seam Requests

Requests from Work Packages for changes to lead-owned files.

## WP-C

### 1. App.tsx — surface the Metrics/ClusterHealth panels in the UI

**Request**: Add import and render of `MetricsPanel` and `ClusterHealthPanel` into `App.tsx`.

**Why**: WP-C owns `MetricsPanel` (per-server gauges) and `ClusterHealthPanel`
(cluster-wide status). These components are fully implemented and tested.
Without wiring them into `App.tsx` the UI doesn't surface observability data
to end users even though the backend endpoints are live.

**Suggested placement**:
- `ClusterHealthPanel` — in a new "Cluster" section above or below "My Servers"
  (it uses its own polling; no extra props needed).
- `MetricsPanel` — inside each `ServerCard` row (or directly in the `servers.map`
  loop), passing `serverName={s.name}`. The panel polls independently; it needs
  no extra state.

**Imports to add**:
```ts
import { MetricsPanel } from "./components/MetricsPanel";
import { ClusterHealthPanel } from "./components/ClusterHealthPanel";
```

**Example render for ClusterHealthPanel** (after the "My Servers" section):
```tsx
<section className="mt-6">
  <ClusterHealthPanel />
</section>
```

**Example render for MetricsPanel** (inside the servers.map, after StatusPill):
```tsx
<MetricsPanel serverName={s.name} />
```

### 2. values.yaml — optional metrics toggle (nice-to-have)

**Request**: Add a `metrics.enabled` boolean (default `true`) so operators can
disable the metrics-server RBAC grants and kubelet proxy calls in environments
where metrics-server is not installed.

**Suggested addition to `values.yaml`**:
```yaml
metrics:
  enabled: true   # set false if metrics-server is not installed
```

**Usage in rbac.yaml** (conditional block around the WP-C rules):
```yaml
{{- if .Values.metrics.enabled }}
  - apiGroups: ["metrics.k8s.io"]
    ...
{{- end }}
```

This is a nice-to-have; the current unconditional RBAC is safe and correct.
