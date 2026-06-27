#!/usr/bin/env bash
# Remove QuetzelPanel cleanly.
#
#   ./uninstall.sh           # remove the platform release (keeps CRD + GameServers)
#   PURGE=1 ./uninstall.sh   # also delete all GameServers, the CRD, and the namespace
set -euo pipefail

RELEASE="${RELEASE:-quetzel}"
NAMESPACE="${NAMESPACE:-quetzel}"

log()  { printf '\033[1;36m>> %s\033[0m\n' "$*"; }

if helm -n "$NAMESPACE" status "$RELEASE" >/dev/null 2>&1; then
  log "helm uninstall $RELEASE"
  helm uninstall "$RELEASE" -n "$NAMESPACE"
else
  log "release $RELEASE not found; nothing to uninstall"
fi

if [ "${PURGE:-0}" = "1" ]; then
  log "PURGE=1 — deleting GameServers, CRD and namespace"
  # Delete CRs first so finalizers/children are reconciled away before the CRD goes.
  kubectl -n "$NAMESPACE" delete gameservers --all --ignore-not-found --timeout=120s || true
  kubectl delete crd gameservers.quetzel.gg --ignore-not-found
  kubectl delete namespace "$NAMESPACE" --ignore-not-found
else
  log "kept the GameServer CRD and any GameServers (data safety)."
  log "  re-run with PURGE=1 to remove everything."
fi

log "done."
