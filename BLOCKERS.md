# BLOCKERS

## B1 — k3s apiserver never comes up (Rancher Desktop / WSL2)  [OPEN]
**Symptom:** `kubectl get nodes` → `dial tcp 127.0.0.1:6443: connectex: No connection ... actively refused`.
The `Rancher Desktop` GUI processes are running (PIDs seen), but `wsl -l -v` shows the
`rancher-desktop` and `rancher-desktop-data` distros stuck in **Stopped**, so k3s never boots and
:6443 is never bound. `docker`/`nerdctl` also fail (VM not up).

**What was tried:**
- `rdctl start` (no args) → "no settings to change were given" (backend control server reachable but VM down).
- `rdctl start --path "...Rancher Desktop.exe" --kubernetes.enabled --application.start-in-background`
  → "Rancher Desktop is already running"; GUI processes spawn but distros stay Stopped.
- Polled `kubectl get nodes` / `/readyz` for ~4+ min → apiserver never bound :6443.

**Diagnosis (hypothesis):** Rancher Desktop's WSL backend integration is failing to start the
`rancher-desktop` distro (possible WSL subsystem / vmmem / corrupted distro state). Needs a manual
RD restart / factory reset / `wsl --shutdown` from the user's interactive session — not resolvable
purely from this non-interactive shell.

**Decision (user-directed, 2026-06-26):** Do NOT keep fighting WSL. **Mock the Kubernetes layer**
behind the backend's provider interface and get the frontend working end-to-end against the mock.
The real `K8sProvider` + operator + CRD + Helm chart remain the target and drop in unchanged once
the cluster is healthy (set `QUETZEL_PROVIDER=k8s`).
