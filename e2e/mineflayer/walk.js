// Shared join+walk routine used by bot.js (single) and harness.js (pooled).
//
// joinAndWalk connects a mineflayer bot (offline auth), waits for spawn, sprints
// while wandering its yaw + jumping, asserts it actually moved, then disconnects.
// Resolves {username, moved, version, start, end} or rejects with an Error.
const mineflayer = require("mineflayer");

const dist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function joinAndWalk({
  host,
  port,
  username,
  version,
  walkMs = 8000,
  spawnTimeoutMs = 60000,
  minBlocks = 2,
  log = () => {},
}) {
  return new Promise((resolve, reject) => {
    const opts = { host, port, username, auth: "offline" };
    if (version) opts.version = version; // per-server version-aware; auto-detect if absent
    const bot = mineflayer.createBot(opts);

    let settled = false;
    const finish = (fn, arg) => {
      if (settled) return;
      settled = true;
      fn(arg);
    };

    const timer = setTimeout(() => {
      try { bot.quit(); } catch (_) {}
      finish(reject, new Error(`${username}: timed out before spawn (${spawnTimeoutMs}ms)`));
    }, spawnTimeoutMs);

    bot.on("kicked", (r) => { clearTimeout(timer); finish(reject, new Error(`${username}: kicked ${JSON.stringify(r)}`)); });
    bot.on("error", (e) => { clearTimeout(timer); finish(reject, new Error(`${username}: ${e && e.message ? e.message : e}`)); });

    bot.once("spawn", async () => {
      clearTimeout(timer);
      try {
        // On a freshly-generated world the spawn chunks may not be loaded yet;
        // the server rejects movement until they arrive. Best-effort wait (its
        // own 10s timeout rejection is non-fatal), then poll-until-moved within a
        // generous deadline so slow servers just take longer, never falsely FAIL.
        if (typeof bot.waitForChunksToLoad === "function") {
          try { await bot.waitForChunksToLoad(); } catch (_) {}
        }
        await sleep(1000);
        const start = bot.entity.position.clone();
        log(`${username}: spawned on ${bot.version} at (${start.x.toFixed(1)},${start.y.toFixed(1)},${start.z.toFixed(1)})`);
        bot.setControlState("sprint", true);
        bot.setControlState("forward", true);
        const deadline = Date.now() + Math.max(walkMs, 30000); // room for slow chunk delivery
        let yaw = bot.entity.yaw;
        let moved = 0;
        while (Date.now() < deadline) {
          yaw += (Math.random() - 0.5) * 1.2;
          await bot.look(yaw, 0, false);
          bot.setControlState("jump", true);
          await sleep(250);
          bot.setControlState("jump", false);
          await sleep(450);
          moved = dist(start, bot.entity.position);
          if (moved >= minBlocks) break; // moved enough -> done early
        }
        bot.setControlState("forward", false);
        bot.setControlState("sprint", false);
        await sleep(300);
        moved = dist(start, bot.entity.position.clone());
        const ver = bot.version;
        try { bot.quit(); } catch (_) {}
        if (moved < minBlocks) {
          return finish(reject, new Error(`${username}: barely moved (${moved.toFixed(2)} blocks)`));
        }
        finish(resolve, { username, moved, version: ver, start, end: bot.entity.position });
      } catch (e) {
        try { bot.quit(); } catch (_) {}
        finish(reject, new Error(`${username}: ${e && e.message ? e.message : e}`));
      }
    });
  });
}

module.exports = { joinAndWalk };
