# SEAM_REQUESTS — cross-work-package seam edits

This file documents any changes WPs made to lead-owned or shared files. The lead
reviews these before merging.

---

## WP-B — player-based game sizing

### `backend/app/providers/k8s.py`

**Why:** The `create_server` method builds the GameServer CR body. Without this
change, `options.maxPlayers` was silently dropped and never included in the CR
`spec`, so the operator could never compute player-based resources.

**Change (minimal):** In `K8sProvider.create_server`, after building `spec`, if
`opts.get("maxPlayers") is not None`, cast it to `int` and add it as
`spec["maxPlayers"]`. This mirrors what `MockProvider` already did (line 121 of
mock.py: `maxPlayers=opts.get("maxPlayers")`).

**File:** `backend/app/providers/k8s.py`  
**Lines changed:** `create_server` body — replaced the inline `body["spec"]` dict
literal with a `spec` variable so `maxPlayers` can be conditionally appended.

### `operator/quetzel_operator/handlers.py`

**No change required.** The kopf `reconcile` handler already passes the full kopf
`spec` mapping (which mirrors the CR spec) into `_ensure_statefulset` →
`manifests.build_statefulset(name, ns, spec, game, ...)`. Since the CR now carries
`spec.maxPlayers` (written by `k8s.py` above), it flows through automatically.

Verified by reading `handlers.py` lines 87–104 and 134–148.
