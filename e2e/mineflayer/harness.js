// Pooled multi-bot harness: N bots x M servers, per-server version-aware.
//
// Reads a JSON config (path as argv[2], $HARNESS_CONFIG, or stdin):
//   {
//     "botsPerServer": 2,
//     "walkMs": 8000,
//     "servers": [
//       { "name": "acme-mc1", "host": "127.0.0.1", "port": 25565, "version": "1.20.4" },
//       ...
//     ]
//   }
// Spawns all bots concurrently, each joins+walks, then teardown. Prints per-bot
// PASS/FAIL and exits 0 only if EVERY bot succeeded (>=1 per server required).
const fs = require("fs");
const { joinAndWalk } = require("./walk");

function loadConfig() {
  const path = process.argv[2] || process.env.HARNESS_CONFIG;
  const raw = path && path !== "-" ? fs.readFileSync(path, "utf8") : fs.readFileSync(0, "utf8");
  return JSON.parse(raw);
}

function botName(server, i) {
  // MC usernames are <=16 chars; keep them unique + readable.
  return `${server}-b${i + 1}`.replace(/[^A-Za-z0-9_]/g, "").slice(0, 16);
}

async function main() {
  const cfg = loadConfig();
  const botsPerServer = cfg.botsPerServer || 2;
  const walkMs = cfg.walkMs || 8000;
  const spawnTimeoutMs = cfg.spawnTimeoutMs || 150000;
  const servers = cfg.servers || [];
  if (servers.length === 0) {
    console.error("harness: no servers in config");
    process.exit(2);
  }

  console.log(`harness: ${servers.length} servers x ${botsPerServer} bots = ${servers.length * botsPerServer} total`);

  const tasks = [];
  for (const s of servers) {
    for (let i = 0; i < botsPerServer; i++) {
      const username = botName(s.name, i);
      tasks.push(
        joinAndWalk({ host: s.host, port: s.port, username, version: s.version, walkMs, spawnTimeoutMs, log: (m) => console.log("  ", m) })
          .then((r) => ({ server: s.name, username, ok: true, moved: r.moved, version: r.version }))
          .catch((e) => ({ server: s.name, username, ok: false, error: e.message }))
      );
    }
  }

  const results = await Promise.all(tasks);

  // Per-server tally: require >=1 bot ok per server (caller sets botsPerServer>=2).
  const byServer = {};
  for (const r of results) {
    (byServer[r.server] = byServer[r.server] || []).push(r);
  }

  let fail = 0;
  console.log("\n--- per-bot results ---");
  for (const r of results) {
    if (r.ok) console.log(`PASS ${r.server.padEnd(14)} ${r.username.padEnd(16)} moved=${r.moved.toFixed(1)} v=${r.version}`);
    else {
      fail++;
      console.error(`FAIL ${r.server.padEnd(14)} ${r.username.padEnd(16)} ${r.error}`);
    }
  }

  console.log("\n--- per-server ---");
  for (const [name, rs] of Object.entries(byServer)) {
    const ok = rs.filter((r) => r.ok).length;
    console.log(`${ok === rs.length ? "OK  " : "BAD "} ${name}: ${ok}/${rs.length} bots walked`);
  }

  const total = results.length;
  console.log(`\nharness: ${total - fail}/${total} bots ok`);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("harness error:", e && e.message ? e.message : e);
  process.exit(1);
});
