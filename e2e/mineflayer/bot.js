// E2E liveness proof for a single QuetzelPanel-deployed Minecraft server.
//
// A mineflayer bot joins (offline auth), confirms it's a real MC world, and WALKS,
// asserting its position changed. Exits non-zero if it can't join or doesn't move.
// (The pooled N-bots x M-servers form lives in harness.js; both share walk.js.)
//
//   MC_HOST=127.0.0.1 MC_PORT=25565 node bot.js
const { joinAndWalk } = require("./walk");

const HOST = process.env.MC_HOST || "127.0.0.1";
const PORT = parseInt(process.env.MC_PORT || "25565", 10);
const USER = process.env.MC_USER || "QuetzelBot";
const VERSION = process.env.MC_VERSION || undefined;
const WALK_MS = parseInt(process.env.WALK_MS || "10000", 10);

console.log(`[bot] connecting to ${HOST}:${PORT} as ${USER} (offline)`);

joinAndWalk({ host: HOST, port: PORT, username: USER, version: VERSION, walkMs: WALK_MS, log: (m) => console.log("[bot]", m) })
  .then((r) => {
    console.log(`[bot] horizontal distance walked = ${r.moved.toFixed(2)} blocks (server ${r.version})`);
    console.log("PASS: bot joined and walked around the deployed server.");
    process.exit(0);
  })
  .catch((e) => {
    console.error("FAIL:", e.message);
    process.exit(1);
  });
