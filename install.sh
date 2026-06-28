#!/usr/bin/env bash
# QuetzelPanel installer — idempotent. Run from WSL2 (or any shell with kubectl/
# helm and a container engine on PATH) against a running Rancher Desktop / k3s.
#
#   ./install.sh                 # deploy PUBLISHED GHCR images (chart appVersion)
#   ./install.sh --local         # build local quetzel/*:<tag> images and deploy those
#   ./install.sh --local --skip-build   # reuse already-built local images
#   PROFILE=prod ./install.sh    # also bootstrap MetalLB/Longhorn/etc (stub)
#
# Image source:
#   default            -> chart's GHCR defaults: ghcr.io/<owner>/quetzel-*:<appVersion>
#   --local / LOCAL_IMAGES=1 -> local images quetzel/operator|backend|frontend:<TAG>
#
# Re-running converges with no drift (helm upgrade --install + cached image builds).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

RELEASE="${RELEASE:-quetzel}"
NAMESPACE="${NAMESPACE:-quetzel}"
CHART="charts/quetzel"
PROFILE="${PROFILE:-local}"
TAG="${TAG:-dev}"
LOCAL_IMAGES="${LOCAL_IMAGES:-0}"

# --- flags -------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --local)      LOCAL_IMAGES=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    --profile)    PROFILE="$2"; shift ;;
    --tag)        TAG="$2"; shift ;;
    -h|--help)
      sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

log()  { printf '\033[1;36m>> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m!! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31mxx %s\033[0m\n' "$*" >&2; exit 1; }

# 1. required CLIs ------------------------------------------------------------
require() { command -v "$1" >/dev/null 2>&1 || die "missing '$1' on PATH. Install it and re-run."; }
log "checking prerequisites"
require kubectl
require helm
if ! command -v nerdctl >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
  die "need a container engine (nerdctl preferred, or docker) on PATH."
fi

# 2. cluster reachable + flavor ----------------------------------------------
log "checking cluster connectivity"
kubectl cluster-info >/dev/null 2>&1 || die "cannot reach a cluster. Is Rancher Desktop / k3s running? (kubectl cluster-info)"
if kubectl get nodes -o wide 2>/dev/null | grep -qi k3s; then
  log "detected k3s — using bundled ServiceLB (Klipper), local-path, Traefik"
else
  warn "non-k3s cluster: ensure a LoadBalancer provider, default StorageClass and an ingress controller exist"
fi
kubectl get storageclass 2>/dev/null | grep -q '(default)' || warn "no default StorageClass detected — PVCs may stay Pending"

# 3. prod-profile prerequisites (stub; not exercised locally) -----------------
if [ "$PROFILE" = "prod" ]; then
  warn "PROFILE=prod: bootstrapping prod prerequisites (MetalLB/Longhorn/ingress-nginx/cert-manager)"
  warn "  -> stubbed: wire real installs here for bare-metal. Skipping on this run."
  # Example (intentionally left commented for local safety):
  # helm repo add metallb https://metallb.github.io/metallb && helm upgrade --install metallb metallb/metallb -n metallb-system --create-namespace
  # helm repo add longhorn https://charts.longhorn.io && helm upgrade --install longhorn longhorn/longhorn -n longhorn-system --create-namespace
fi

# 4. render the catalog from the canonical source (single source of truth) ----
if command -v python3 >/dev/null 2>&1; then
  log "exporting catalog from backend/app/catalog.py"
  ( cd backend && python3 -c "import json,sys; sys.path.insert(0,'.'); from app import catalog; d=json.dumps({'games':catalog.list_games()},indent=2); open('../deploy/catalog.json','w').write(d); open('../charts/quetzel/files/catalog.json','w').write(d)" ) \
    || warn "catalog export failed; using committed charts/quetzel/files/catalog.json"
else
  warn "python3 not found; using committed charts/quetzel/files/catalog.json"
fi

# 5. build images into the k3s-visible store (local mode only) ----------------
IMAGE_ARGS=()
if [ "$LOCAL_IMAGES" = "1" ]; then
  if [ "${SKIP_BUILD:-0}" != "1" ]; then
    log "building local images (TAG=$TAG)"
    TAG="$TAG" ./build-images.sh
  else
    log "SKIP_BUILD=1 — reusing existing local images"
  fi
  IMAGE_ARGS=(
    --set operator.image="quetzel/operator:${TAG}"
    --set backend.image="quetzel/backend:${TAG}"
    --set frontend.image="quetzel/frontend:${TAG}"
  )
else
  log "using published GHCR images (chart appVersion). Pass --local to build/use local images."
fi

# 6. install / upgrade the platform -------------------------------------------
log "helm upgrade --install $RELEASE -> namespace $NAMESPACE (profile $PROFILE)"
helm upgrade --install "$RELEASE" "$CHART" \
  --namespace "$NAMESPACE" --create-namespace \
  --set profile="$PROFILE" \
  "${IMAGE_ARGS[@]}" \
  ${HELM_EXTRA_ARGS:-} \
  --wait --timeout 300s

# 7. wait for rollouts --------------------------------------------------------
log "waiting for rollouts"
for d in quetzel-operator quetzel-backend quetzel-frontend; do
  kubectl -n "$NAMESPACE" rollout status deploy/"$d" --timeout=180s
done

# 8. print how to open it -----------------------------------------------------
HOST="$(helm -n "$NAMESPACE" get values "$RELEASE" -a -o json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("ingress",{}).get("host","quetzel.localhost"))' 2>/dev/null || echo quetzel.localhost)"
EXTIP="$(kubectl -n "$NAMESPACE" get svc -l app.kubernetes.io/part-of=quetzelpanel -o jsonpath='{range .items[*]}{.status.loadBalancer.ingress[0].ip}{"\n"}{end}' 2>/dev/null | head -n1 || true)"
echo
log "QuetzelPanel is installed."
echo "   UI (ingress):     http://${HOST}/"
echo "   UI (port-forward): kubectl -n ${NAMESPACE} port-forward svc/quetzel-frontend 8080:80  ->  http://localhost:8080/"
echo "   Servers:          kubectl -n ${NAMESPACE} get gameservers"
