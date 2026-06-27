// k6 smoke test — 1 VU, a few iterations. Fast sanity that the API is up and the
// core read endpoints behave. Run:  k6 run k6/smoke.js
import http from "k6/http";
import { check } from "k6";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";

export const options = {
  vus: 1,
  iterations: 5,
  thresholds: {
    http_req_failed: ["rate==0"],
    checks: ["rate==1.0"],
  },
};

export default function () {
  const health = http.get(`${BASE}/healthz`);
  check(health, {
    "healthz 200": (r) => r.status === 200,
    "healthz ok": (r) => r.json("status") === "ok",
  });

  const games = http.get(`${BASE}/games`);
  check(games, {
    "games 200": (r) => r.status === 200,
    "games >= 2": (r) => r.json("games").length >= 2,
  });
}
