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

if command -v nerdctl >/dev/null 2>&1; then
  build_with_nerdctl
elif command -v docker >/dev/null 2>&1; then
  build_with_docker
else
  echo "ERROR: neither nerdctl nor docker found on PATH." >&2
  exit 1
fi

echo ">> done: quetzel/{operator,backend,frontend}:${TAG}"
