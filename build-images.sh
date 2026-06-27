#!/usr/bin/env bash
# Build the three platform images so k3s can run them.
#
# Rancher Desktop gotcha: host-built images must land in the SAME image store k3s
# pulls from. With the containerd engine that's the `k8s.io` namespace, reachable
# via `nerdctl --namespace k8s.io`. With the dockerd/moby engine, images are NOT
# shared with k3s automatically — switch Rancher Desktop to containerd (preferred)
# or this script will warn and build with docker as a best effort.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

TAG="${TAG:-dev}"
IMG_NS="${IMG_NS:-k8s.io}"
images_built=()

build_with_nerdctl() {
  echo ">> building images with nerdctl into containerd namespace '$IMG_NS'"
  nerdctl --namespace "$IMG_NS" build -t "quetzel/operator:${TAG}" -f operator/Dockerfile .
  nerdctl --namespace "$IMG_NS" build -t "quetzel/backend:${TAG}"  -f backend/Dockerfile .
  nerdctl --namespace "$IMG_NS" build -t "quetzel/frontend:${TAG}" -f frontend/Dockerfile .
}

build_with_docker() {
  echo "!! nerdctl not found — falling back to docker."
  echo "!! If k3s can't pull the images, switch Rancher Desktop to the containerd engine."
  docker build -t "quetzel/operator:${TAG}" -f operator/Dockerfile .
  docker build -t "quetzel/backend:${TAG}"  -f backend/Dockerfile .
  docker build -t "quetzel/frontend:${TAG}" -f frontend/Dockerfile .
}

# Pick the engine that shares an image store with k3s, based on the node runtime:
#   docker://...     -> Rancher Desktop dockerd mode: `docker build` is visible to k3s
#   containerd://... -> containerd mode: build into the k8s.io namespace via nerdctl
RUNTIME="$(kubectl get nodes -o jsonpath='{.items[0].status.nodeInfo.containerRuntimeVersion}' 2>/dev/null || true)"
echo ">> k3s node runtime: ${RUNTIME:-unknown}"

case "$RUNTIME" in
  docker://*)
    command -v docker >/dev/null 2>&1 || { echo "ERROR: dockerd-mode cluster but no docker CLI." >&2; exit 1; }
    build_with_docker
    ;;
  containerd://*)
    command -v nerdctl >/dev/null 2>&1 || { echo "ERROR: containerd-mode cluster but no nerdctl CLI." >&2; exit 1; }
    build_with_nerdctl
    ;;
  *)
    # Unknown/unreachable runtime — prefer nerdctl(k8s.io), fall back to docker.
    if command -v nerdctl >/dev/null 2>&1 && nerdctl --namespace "$IMG_NS" images >/dev/null 2>&1; then
      build_with_nerdctl
    elif command -v docker >/dev/null 2>&1; then
      build_with_docker
    else
      echo "ERROR: no usable container engine found." >&2
      exit 1
    fi
    ;;
esac

echo ">> done: quetzel/{operator,backend,frontend}:${TAG}"
