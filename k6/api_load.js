// k6 load test for the QuetzelPanel backend API.
//
// Two concurrent scenarios:
//   browse    — read-heavy traffic (healthz, games, servers list), ramps to 15 VUs
//   lifecycle — full create -> get -> delete CRUD churn at a steady concurrency
//
// Run against the local backend (default) or any URL:
//   k6 run k6/api_load.js
//   k6 run -e BASE_URL=http://192.168.127.2:30080 k6/api_load.js
import http from "k6/http";
import { check, group } from "k6";
import { Trend } from "k6/metrics";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";
const JSON_HEADERS = { headers: { "Content-Type": "application/json" } };

const createLatency = new Trend("quetzel_create_latency", true);

export const options = {
  scenarios: {
    browse: {
      executor: "ramping-vus",
      exec: "browse",
      startVUs: 0,
      stages: [
        { duration: "10s", target: 15 },
        { duration: "15s", target: 15 },
        { duration: "5s", target: 0 },
      ],
    },
    lifecycle: {
      executor: "constant-vus",
      exec: "lifecycle",
      vus: 4,
      duration: "30s",
      startTime: "0s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.01"], // <1% errors
    http_req_duration: ["p(95)<500"], // 95% of requests under 500ms
    checks: ["rate>0.99"], // >99% of checks pass
    quetzel_create_latency: ["p(95)<800"],
  },
};

export function browse() {
  group("browse", () => {
    const h = http.get(`${BASE}/healthz`);
    check(h, { "healthz 200": (r) => r.status === 200 });

    const g = http.get(`${BASE}/games`);
    check(g, {
      "games 200": (r) => r.status === 200,
      "games >= 2": (r) => r.json("games").length >= 2,
    });

    const s = http.get(`${BASE}/servers`);
    check(s, { "servers 200": (r) => r.status === 200 });
  });
}

export function lifecycle() {
  group("lifecycle", () => {
    const name = `k6-lc-${__VU}-${__ITER}`;
    const payload = JSON.stringify({
      name,
      game: "minecraft",
      options: { version: "1.21.1" },
    });

    const created = http.post(`${BASE}/servers`, payload, JSON_HEADERS);
    createLatency.add(created.timings.duration);
    const ok = check(created, {
      "create 201": (r) => r.status === 201,
      "create returns name": (r) => r.json("name") === name,
    });
    if (!ok) return;

    const got = http.get(`${BASE}/servers/${name}`);
    check(got, {
      "get 200": (r) => r.status === 200,
      "has phase": (r) =>
        ["Pending", "Provisioning", "Running"].includes(r.json("status.phase")),
    });

    const del = http.del(`${BASE}/servers/${name}`);
    check(del, { "delete 204": (r) => r.status === 204 });
  });
}
