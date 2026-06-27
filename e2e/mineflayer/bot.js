// E2E liveness proof for a QuetzelPanel-deployed Minecraft server.
//
// A mineflayer bot joins (offline auth), confirms it's a real MC world (version,
// player list, spawn position), then WALKS: it sprints forward while wandering its
// yaw and jumping, and asserts its position actually changed. Exits non-zero if it
// can't join or doesn't move — so this doubles as an automated check.
//
//   MC_HOST=127.0.0.1 MC_PORT=25565 node bot.js
const mineflayer = require("mineflayer");

const HOST = process.env.MC_HOST || "127.0.0.1";
const PORT = parseInt(process.env.MC_PORT || "25565", 10);
const USER = process.env.MC_USER || "QuetzelBot";
const WALK_MS = parseInt(process.env.WALK_MS || "10000", 10);

const dist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function fail(msg) {
  console.error("FAIL:", msg);
  process.exit(1);
}

console.log(`[bot] connecting to ${HOST}:${PORT} as ${USER} (offline)`);

const bot = mineflayer.createBot({
  host: HOST,
  port: PORT,
  username: USER,
  auth: "offline",
  // version auto-detected from the server during the ping/handshake
});

const kickTimer = setTimeout(() => fail("timed out before spawn (60s)"), 60000);

bot.on("kicked", (reason) => fail("kicked: " + JSON.stringify(reason)));
bot.on("error", (err) => fail("error: " + (err && err.message ? err.message : err)));
bot.on("end", (reason) => console.log("[bot] disconnected:", reason));

bot.once("spawn", async () => {
  clearTimeout(kickTimer);
  try {
    console.log(`[bot] SPAWNED. server version = ${bot.version}`);
    console.log(`[bot] players online = ${Object.keys(bot.players).join(", ") || "(none listed yet)"}`);

    const start = bot.entity.position.clone();
    console.log(`[bot] start position = (${start.x.toFixed(1)}, ${start.y.toFixed(1)}, ${start.z.toFixed(1)})`);

    bot.chat("QuetzelBot online — going for a walk.");

    // Walk: sprint forward, wander the yaw, jump periodically.
    bot.setControlState("sprint", true);
    bot.setControlState("forward", true);

    const deadline = Date.now() + WALK_MS;
    let yaw = bot.entity.yaw;
    while (Date.now() < deadline) {
      yaw += (Math.random() - 0.5) * 1.2;
      await bot.look(yaw, 0, false);
      bot.setControlState("jump", true);
      await sleep(250);
      bot.setControlState("jump", false);
      await sleep(550);
    }

    bot.setControlState("forward", false);
    bot.setControlState("sprint", false);
    await sleep(500);

    const end = bot.entity.position.clone();
    const moved = dist(start, end);
    console.log(`[bot] end position   = (${end.x.toFixed(1)}, ${end.y.toFixed(1)}, ${end.z.toFixed(1)})`);
    console.log(`[bot] horizontal distance walked = ${moved.toFixed(2)} blocks`);

    bot.chat(`Walked ${moved.toFixed(1)} blocks. Logging off.`);
    await sleep(500);

    if (moved < 2) fail(`bot barely moved (${moved.toFixed(2)} blocks) — not convincingly walking`);

    console.log("PASS: bot joined and walked around the deployed server.");
    bot.quit();
    setTimeout(() => process.exit(0), 500);
  } catch (e) {
    fail("exception during walk: " + (e && e.message ? e.message : e));
  }
});
