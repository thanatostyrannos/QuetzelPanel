#!/usr/bin/env bash
# QuetzelPanel grand E2E — the machine-checkable finish line (§5).
#
#   ./e2e/verify.sh            # full: 2 customers x 2 servers x >=2 bots (live)
#   ./e2e/verify.sh --smoke    # CI/k3d: 1 customer x 1 server x 1 bot, smallest tier
#   ./e2e/verify.sh --reset    # delete the e2e servers and exit (clean slate)
#   ./e2e/verify.sh --require-all   # treat capability-gated SKIPs as FAIL (Phase 3)
#
# CONVERGENT + IDEMPOTENT: reconciles to the desired set by stable name (reuse or
# create). Re-running does not accumulate duplicates. Exits 0 only if every RUN
# gate passes. Capability-aware: gates whose features aren't merged yet print SKIP
# (so this same script runs from Phase 0 through Phase 3) unless --require-all.
#
# This script is the source of truth (Engineering standard 8); STATE.md records
# its real output. It is NOT an open-ended loop: liveness waits are bounded.
set -uo pipefail

# ----------------------------------------------------------------------------- config
NS="${QUETZEL_NS:-quetzel}"
API="${QUETZEL_API:-}"                       # if empty -> port-forward quetzel-backend
LIVENESS_TIMEOUT="${LIVENESS_TIMEOUT:-600}"  # seconds (default 10 min, §5 gate 2)
WALK_MS="${WALK_MS:-8000}"
MC_VERSION="${MC_VERSION:-1.20.4}"           # one version for all servers (§5: vary size, not version)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SMOKE=0; RESET=0; REQUIRE_ALL=0
for a in "$@"; do
  case "$a" in
    --smoke) SMOKE=1 ;;
    --reset) RESET=1 ;;
    --require-all) REQUIRE_ALL=1 ;;
    *) echo "unknown flag: $a" >&2; exit 2 ;;
  esac
done

# Desired topology. Rows: customer|cust_id|server|maxPlayers
# Distinct maxPlayers => distinct computed resources (§5 gate 1). Smallest tiers.
if [ "$SMOKE" = "1" ]; then
  BOTS_PER_SERVER=1
  TOPOLOGY=( "acme|acme|acme-mc1|2" )
else
  BOTS_PER_SERVER=2
  TOPOLOGY=(
    "acme|acme|acme-mc1|2"
    "acme|acme|acme-mc2|4"
    "globex|globex|globex-mc1|6"
    "globex|globex|globex-mc2|8"
  )
fi

# ----------------------------------------------------------------------------- output
ok=0; bad=0; skip=0
declare -a SUMMARY
note()  { printf '\033[1;36m>> %s\033[0m\n' "$*"; }
pass()  { printf '\033[1;32mPASS\033[0m %s\n' "$*"; SUMMARY+=("PASS $*"); ok=$((ok+1)); }
fail()  { printf '\033[1;31mFAIL\033[0m %s\n' "$*"; SUMMARY+=("FAIL $*"); bad=$((bad+1)); }
skipg() { printf '\033[1;33mSKIP\033[0m %s\n' "$*"; SUMMARY+=("SKIP $*"); skip=$((skip+1)); }

PF_PIDS=()
cleanup() { for p in "${PF_PIDS[@]:-}"; do kill "$p" >/dev/null 2>&1 || true; done; }
trap cleanup EXIT

# ----------------------------------------------------------------------------- api
JWT=""   # set per call when auth is enabled
api() { # api METHOD PATH [JSON_BODY] -> body on stdout, http code in $API_CODE
  local method="$1" path="$2" body="${3:-}"
  local args=(-s -o /tmp/qz_body -w '%{http_code}' -X "$method" "${API}${path}" -H 'Content-Type: application/json')
  [ -n "$JWT" ] && args+=(-H "Authorization: Bearer ${JWT}")
  [ -n "$body" ] && args+=(--data "$body")
  API_CODE="$(curl "${args[@]}" 2>/dev/null)"
  cat /tmp/qz_body
}

start_backend_pf() {
  if [ -n "$API" ]; then note "using API at $API"; return; fi
  note "port-forwarding svc/quetzel-backend -> 127.0.0.1:18000"
  kubectl -n "$NS" port-forward svc/quetzel-backend 18000:8000 >/tmp/qz_pf_backend.log 2>&1 &
  PF_PIDS+=("$!")
  API="http://127.0.0.1:18000"
  for _ in $(seq 1 30); do
    curl -sf "${API}/healthz" >/dev/null 2>&1 && return 0
    sleep 1
  done
  fail "backend API not reachable via port-forward"; print_summary; exit 1
}

# ----------------------------------------------------------------------------- capability probes
CAP_AUTH=0 CAP_SIZING=0
probe_caps() {
  # auth is ENFORCED (not just implemented) iff an unauthenticated /servers is
  # rejected. In permissive/mock deploys it returns 200 -> CAP_AUTH=0 (seed +
  # tenancy skipped). With JWT_SECRET set it returns 401 -> CAP_AUTH=1.
  JWT=""
  api GET /servers >/dev/null
  [ "$API_CODE" = "401" ] && CAP_AUTH=1
  # sizing present if the operator's compute_resources is implemented
  if python_compute 2 >/dev/null 2>&1; then CAP_SIZING=1; fi
  note "capabilities: auth=$CAP_AUTH sizing=$CAP_SIZING (smoke=$SMOKE require_all=$REQUIRE_ALL)"
}

python_compute() { # python_compute MAXPLAYERS -> "<cpu> <memory>" (requests) from compute_resources
  local mp="$1"
  ( cd "$REPO_ROOT" && python3 - "$mp" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "backend"); sys.path.insert(0, "operator")
from app import catalog
from quetzel_operator.manifests import compute_resources
mp = int(sys.argv[1])
r = compute_resources(catalog.get_game("minecraft")["sizing"], mp)
print(r["requests"]["cpu"], r["requests"]["memory"], r["limits"]["cpu"], r["limits"]["memory"])
PY
  )
}

# ----------------------------------------------------------------------------- auth seeding (WP-A/D)
declare -A CUST_JWT   # cust_id -> a customer-user JWT
ADMIN_JWT=""
seed_identities() {
  [ "$CAP_AUTH" = "1" ] || { note "auth not enabled — operating unauthenticated (permissive)"; return; }
  note "seeding customers + users + JWTs via API"
  # Admin bootstrap + per-customer user. Endpoints are the WP-A/D contract:
  #   POST /auth/login {username,password} -> {token}
  #   POST /customers {id,name} (admin)        POST /auth/users {username,password,role,customerId} (admin)
  ADMIN_JWT="$(get_jwt "${QZ_ADMIN_USER:-admin}" "${QZ_ADMIN_PASS:-admin}")"
  JWT="$ADMIN_JWT"
  local seen=""
  for row in "${TOPOLOGY[@]}"; do
    IFS='|' read -r cust cid server mp <<<"$row"
    case " $seen " in *" $cid "*) ;; *)
      seen="$seen $cid"
      api POST /customers "{\"id\":\"$cid\",\"name\":\"$cust\"}" >/dev/null
      api POST /auth/users "{\"username\":\"$cid-user\",\"password\":\"pw-$cid\",\"role\":\"customer-user\",\"customerId\":\"$cid\"}" >/dev/null
      CUST_JWT[$cid]="$(get_jwt "$cid-user" "pw-$cid")"
      ;;
    esac
  done
  JWT=""
}
get_jwt() { # get_jwt USER PASS -> token
  local body; body="$(api POST /auth/login "{\"username\":\"$1\",\"password\":\"$2\"}")"
  echo "$body" | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("token",""))
except Exception: print("")' 2>/dev/null
}

# ----------------------------------------------------------------------------- reconcile (idempotent)
reconcile_servers() {
  note "reconciling ${#TOPOLOGY[@]} servers to desired set (create-or-reuse)"
  for row in "${TOPOLOGY[@]}"; do
    IFS='|' read -r cust cid server mp <<<"$row"
    [ "$CAP_AUTH" = "1" ] && JWT="$ADMIN_JWT"
    api GET "/servers/$server" >/dev/null
    if [ "$API_CODE" = "200" ]; then
      echo "   reuse $server"
    else
      local opts
      # ONLINE_MODE=FALSE so offline mineflayer bots can join (no Mojang auth).
      # FLAT world = instant gen + flat unobstructed ground so bots walk freely
      # and deterministically (world type is irrelevant to the size/tenancy proof).
      # Heap (1024M) sits well under the smallest computed limit (1792Mi) so the
      # JVM + Paper overhead never OOM-CrashLoops the pod.
      opts="{\"version\":\"$MC_VERSION\",\"maxPlayers\":$mp,\"customer\":\"$cid\",\"env\":{\"TYPE\":\"PAPER\",\"VERSION\":\"$MC_VERSION\",\"ONLINE_MODE\":\"FALSE\",\"LEVEL_TYPE\":\"FLAT\",\"GENERATE_STRUCTURES\":\"false\",\"SPAWN_PROTECTION\":\"0\",\"USE_AIKAR_FLAGS\":\"true\",\"MEMORY\":\"1024M\",\"MAX_PLAYERS\":\"$mp\"}}"
      api POST /servers "{\"name\":\"$server\",\"game\":\"minecraft\",\"options\":$opts}" >/dev/null
      if [ "$API_CODE" = "201" ]; then echo "   create $server (maxPlayers=$mp, customer=$cid)"; else echo "   create $server -> HTTP $API_CODE"; fi
    fi
    JWT=""
  done
}

# ----------------------------------------------------------------------------- GATE 2: liveness (bounded)
gate_liveness() {
  note "GATE liveness: waiting for ${#TOPOLOGY[@]} game pods Running (<= ${LIVENESS_TIMEOUT}s)"
  local deadline=$(( $(date +%s) + LIVENESS_TIMEOUT ))
  local pending=("${TOPOLOGY[@]}")
  while [ "${#pending[@]}" -gt 0 ] && [ "$(date +%s)" -lt "$deadline" ]; do
    local still=()
    for row in "${pending[@]}"; do
      IFS='|' read -r cust cid server mp <<<"$row"
      local phase ready
      phase="$(kubectl -n "$NS" get gameserver "$server" -o jsonpath='{.status.phase}' 2>/dev/null)"
      ready="$(kubectl -n "$NS" get pod "${server}-0" -o jsonpath='{.status.containerStatuses[0].ready}' 2>/dev/null)"
      if [ "$ready" = "true" ] || [ "$phase" = "Running" ]; then :; else still+=("$row"); fi
      # hard-fail fast on CrashLoopBackOff
      local waiting
      waiting="$(kubectl -n "$NS" get pod "${server}-0" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null)"
      if [ "$waiting" = "CrashLoopBackOff" ]; then
        kubectl -n "$NS" describe pod "${server}-0" > "/tmp/qz_describe_${server}.txt" 2>&1 || true
        fail "liveness: $server in CrashLoopBackOff (see /tmp/qz_describe_${server}.txt)"
        return
      fi
    done
    pending=("${still[@]}")
    [ "${#pending[@]}" -gt 0 ] && sleep 8
  done
  if [ "${#pending[@]}" -eq 0 ]; then
    pass "liveness: all ${#TOPOLOGY[@]} game pods Running"
  else
    for row in "${pending[@]}"; do IFS='|' read -r _ _ server _ <<<"$row"; kubectl -n "$NS" describe pod "${server}-0" > "/tmp/qz_describe_${server}.txt" 2>&1 || true; done
    fail "liveness: ${#pending[@]} pod(s) not Running within ${LIVENESS_TIMEOUT}s (Pending/insufficient memory => FAIL, see /tmp/qz_describe_*.txt)"
  fi
}

# ----------------------------------------------------------------------------- GATE 1: sizing reached the cluster
gate_sizing() {
  if [ "$CAP_SIZING" != "1" ]; then skipg "sizing: compute_resources not implemented yet (WP-B)"; return; fi
  note "GATE sizing: comparing live StatefulSet resources to compute_resources()"
  local distinct_file=/tmp/qz_sizes.txt; : > "$distinct_file"
  local all_ok=1
  printf '   %-14s %-6s %-28s %-28s\n' SERVER MAXP "LIVE(req cpu/mem)" "EXPECTED(req cpu/mem)"
  for row in "${TOPOLOGY[@]}"; do
    IFS='|' read -r cust cid server mp <<<"$row"
    local live exp
    live="$(kubectl -n "$NS" get statefulset "$server" -o jsonpath='{.spec.template.spec.containers[0].resources.requests.cpu}{"/"}{.spec.template.spec.containers[0].resources.requests.memory}' 2>/dev/null)"
    read -r ecpu emem lcpu lmem <<<"$(python_compute "$mp")"
    exp="${ecpu}/${emem}"
    printf '   %-14s %-6s %-28s %-28s\n' "$server" "$mp" "${live:-<none>}" "$exp"
    echo "$live" >> "$distinct_file"
    [ "$live" = "$exp" ] || all_ok=0
  done
  local distinct; distinct="$(sort -u "$distinct_file" | grep -c . )"
  local want="${#TOPOLOGY[@]}"
  if [ "$SMOKE" = "1" ]; then
    [ "$all_ok" = "1" ] && pass "sizing: live resources match compute_resources()" || fail "sizing: live != computed"
  else
    if [ "$all_ok" = "1" ] && [ "$distinct" -eq "$want" ]; then
      pass "sizing: $want distinct resource sets, each == compute_resources()"
    else
      fail "sizing: all_match=$all_ok distinct=$distinct/$want"
    fi
  fi
}

# ----------------------------------------------------------------------------- GATE 3: connectivity (bots)
gate_connectivity() {
  note "GATE connectivity: port-forwarding servers + running mineflayer harness"
  local localport=25565
  local servers_json=""
  for row in "${TOPOLOGY[@]}"; do
    IFS='|' read -r cust cid server mp <<<"$row"
    kubectl -n "$NS" port-forward "svc/$server" "${localport}:25565" >"/tmp/qz_pf_${server}.log" 2>&1 &
    PF_PIDS+=("$!")
    [ -n "$servers_json" ] && servers_json+=","
    servers_json+="{\"name\":\"$server\",\"host\":\"127.0.0.1\",\"port\":$localport,\"version\":\"$MC_VERSION\"}"
    localport=$((localport+1))
  done
  sleep 5  # let port-forwards establish
  local cfg="/tmp/qz_harness.json"
  echo "{\"botsPerServer\":$BOTS_PER_SERVER,\"walkMs\":$WALK_MS,\"servers\":[$servers_json]}" > "$cfg"

  ( cd "$REPO_ROOT/e2e/mineflayer" && [ -d node_modules ] || npm install --silent >/tmp/qz_npm.log 2>&1 )
  if ( cd "$REPO_ROOT/e2e/mineflayer" && node harness.js "$cfg" ); then
    pass "connectivity: >=${BOTS_PER_SERVER} bot(s)/server joined and walked"
  else
    fail "connectivity: one or more bots failed to join/walk (see output above)"
  fi
}

# ----------------------------------------------------------------------------- GATE 4: tenancy
gate_tenancy() {
  if [ "$CAP_AUTH" != "1" ]; then skipg "tenancy: auth not enabled yet (WP-A/WP-D)"; return; fi
  if [ "$SMOKE" = "1" ]; then skipg "tenancy: single-tenant smoke"; return; fi
  note "GATE tenancy: customer-user sees only own servers; admin sees all"
  local total_ok=1
  # admin sees all 4
  JWT="$ADMIN_JWT"; local admin_count
  admin_count="$(api GET /servers | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null)"
  [ "$admin_count" = "${#TOPOLOGY[@]}" ] || total_ok=0
  # each customer-user sees exactly their own
  for cid in "${!CUST_JWT[@]}"; do
    JWT="${CUST_JWT[$cid]}"
    local want=0
    for row in "${TOPOLOGY[@]}"; do IFS='|' read -r _ rcid _ _ <<<"$row"; [ "$rcid" = "$cid" ] && want=$((want+1)); done
    local got
    got="$(api GET /servers | python3 -c 'import sys,json; print(len(json.load(sys.stdin)))' 2>/dev/null)"
    echo "   $cid-user sees $got (want $want)"
    [ "$got" = "$want" ] || total_ok=0
  done
  JWT=""
  [ "$total_ok" = "1" ] && pass "tenancy: admin sees all, each customer-user sees only its own" || fail "tenancy: scoping mismatch (admin=$admin_count)"
}

# ----------------------------------------------------------------------------- reset
do_reset() {
  start_backend_pf
  for row in "${TOPOLOGY[@]}"; do IFS='|' read -r _ _ server _ <<<"$row"; api DELETE "/servers/$server" >/dev/null; echo "   deleted $server ($API_CODE)"; done
  exit 0
}

print_summary() {
  echo
  echo "================ e2e/verify.sh summary ================"
  for line in "${SUMMARY[@]:-}"; do echo "  $line"; done
  echo "  ---- ok=$ok fail=$bad skip=$skip ----"
  echo "======================================================="
}

# ----------------------------------------------------------------------------- main
note "QuetzelPanel verify ($([ "$SMOKE" = 1 ] && echo smoke || echo full)) — ns=$NS"
command -v kubectl >/dev/null || { echo "kubectl required"; exit 2; }
start_backend_pf
[ "$RESET" = "1" ] && do_reset
probe_caps
seed_identities
reconcile_servers
gate_liveness
# Only assert sizing/connectivity once pods are live; if liveness failed, still try
# sizing (resources are set at create time) but skip connectivity.
gate_sizing
if printf '%s\n' "${SUMMARY[@]}" | grep -q '^FAIL liveness'; then
  skipg "connectivity: skipped (liveness failed)"
else
  gate_connectivity
fi
gate_tenancy

print_summary

# Capability SKIPs only fail the run under --require-all (Phase 3).
if [ "$bad" -gt 0 ]; then exit 1; fi
if [ "$REQUIRE_ALL" = "1" ] && [ "$skip" -gt 0 ]; then echo "require-all: $skip gate(s) skipped"; exit 1; fi
echo "RESULT: PASS"
exit 0
