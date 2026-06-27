# STACK — single source of truth (frozen before P1; do not revisit)

Chosen once per §5. No thrashing.

| Layer | Choice | Notes |
|-------|--------|-------|
| Operator / controller | **Python + kopf** | Declarative reconciler, fast iteration, no codegen. |
| Backend API | **Python + FastAPI** | Same language as operator; shares the in-repo catalog + k8s client helpers. |
| Frontend | **React + Vite + TypeScript + Tailwind** | Modern SPA, game-card grid + My Servers view. |
| Packaging | **Helm chart** (`charts/quetzel`) | `install.sh` wraps `helm upgrade --install`. |
| Image build | **nerdctl into containerd `k8s.io` namespace** | Rancher Desktop containerd store → images visible to k3s with no push. Fallback: `nerdctl save` + `ctr -n k8s.io images import`. |

## CRD identity
- Group/version: `quetzel.gg/v1alpha1`
- Kind: `GameServer` (plural `gameservers`, short `gs`)

## Namespacing
- Platform components + all GameServers live in namespace **`quetzel`**.

## Why Python (kopf+FastAPI) over Go (kubebuilder)
The §5 alt was explicitly offered for faster iteration. In an autonomous loop the dominant
cost is build/debug cycle time and image size; kopf gives a working reconciler in one file with
no scaffolding/codegen, and FastAPI shares the exact same catalog module and k8s client. Go's
type-sharing advantage is real but not worth the toolchain + codegen overhead here for v1.
