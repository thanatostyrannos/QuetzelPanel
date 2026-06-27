import { useEffect, useMemo, useState } from "react";
import type { Game } from "../types";
import { isValidServerName } from "../lib/validation";
import { computeResources, fmtMemory, fmtCpu } from "../lib/sizing";

function suggestName(gameId: string): string {
  const suffix = Math.random().toString(36).slice(2, 6);
  return `${gameId}-${suffix}`;
}

export function DeployModal({
  game,
  busy,
  error,
  onClose,
  onSubmit,
}: {
  game: Game;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: { name: string; game: string; options: Record<string, unknown> }) => void;
}) {
  const [name, setName] = useState(() => suggestName(game.id));
  const [version, setVersion] = useState(game.versions[0]);
  const [storageSize, setStorageSize] = useState("2Gi");
  // WP-B: player count — only shown when the game has a sizing block
  const [maxPlayers, setMaxPlayers] = useState<number>(
    game.sizing?.maxPlayers ?? 20
  );

  useEffect(() => {
    setName(suggestName(game.id));
    setVersion(game.versions[0]);
    setMaxPlayers(game.sizing?.maxPlayers ?? 20);
  }, [game.id]);

  const nameValid = useMemo(() => isValidServerName(name), [name]);

  // WP-B: live resource preview derived from the client-side formula
  const resourcePreview = useMemo(() => {
    if (!game.sizing) return null;
    return computeResources(game.sizing, maxPlayers);
  }, [game.sizing, maxPlayers]);

  const handleMaxPlayersChange = (v: string) => {
    const n = parseInt(v, 10);
    if (!isNaN(n)) {
      const clamped = Math.max(1, Math.min(n, game.sizing?.maxPlayers ?? n));
      setMaxPlayers(clamped);
    }
  };

  return (
    <div
      className="backdrop fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="fade-in w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-ink-900"
        onClick={(e) => e.stopPropagation()}
        style={{ boxShadow: "0 30px 80px -20px rgba(0,0,0,0.9)" }}
      >
        <div
          className="flex items-center gap-3 p-5"
          style={{ background: `linear-gradient(160deg, ${game.accent}33, transparent)` }}
        >
          <span className="text-4xl">{game.icon}</span>
          <div>
            <h2 className="text-xl font-bold text-white">Deploy {game.name}</h2>
            <p className="text-xs text-white/50">{game.image}</p>
          </div>
        </div>

        <div className="flex flex-col gap-4 p-5">
          <label className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold uppercase tracking-wide text-white/50">
              Server name
            </span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value.toLowerCase())}
              className="rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
              placeholder="my-server"
            />
            {!nameValid && (
              <span className="text-xs text-red-400">
                lowercase letters, digits and dashes (1–32 chars)
              </span>
            )}
          </label>

          <div className="grid grid-cols-2 gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-white/50">
                Version
              </span>
              <select
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                className="rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
              >
                {game.versions.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-white/50">
                Storage
              </span>
              <select
                value={storageSize}
                onChange={(e) => setStorageSize(e.target.value)}
                className="rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
              >
                {["1Gi", "2Gi", "5Gi", "10Gi"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {/* WP-B: max-players control + live resource preview */}
          {game.sizing && (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-semibold uppercase tracking-wide text-white/50">
                  Max players
                  <span className="ml-1 font-normal normal-case text-white/30">
                    (1–{game.sizing.maxPlayers})
                  </span>
                </span>
                <input
                  type="number"
                  min={1}
                  max={game.sizing.maxPlayers}
                  value={maxPlayers}
                  onChange={(e) => handleMaxPlayersChange(e.target.value)}
                  aria-label="Max players"
                  className="rounded-lg border border-white/10 bg-ink-800 px-3 py-2 text-sm text-white outline-none focus:border-brand-500"
                />
              </label>
              {resourcePreview && (
                <div
                  className="flex items-center gap-3 rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-xs text-white/60"
                  aria-label="Resource preview"
                >
                  <span className="font-semibold text-white/40 uppercase tracking-wide">
                    Resources
                  </span>
                  <span>
                    CPU{" "}
                    <span className="font-mono text-white/80">
                      {fmtCpu(resourcePreview.requests.cpu)}
                    </span>
                  </span>
                  <span>
                    RAM{" "}
                    <span className="font-mono text-white/80">
                      {fmtMemory(resourcePreview.requests.memory)}
                    </span>
                  </span>
                </div>
              )}
            </div>
          )}

          {game.id === "minecraft" && (
            <div className="rounded-lg border border-amber-400/20 bg-amber-400/5 px-3 py-2 text-xs text-amber-200/80">
              By deploying you accept the Minecraft EULA (<code>EULA=TRUE</code>).
            </div>
          )}

          {game.rcon.enabled && (
            <p className="text-xs text-white/40">
              RCON admin enabled — a password is generated and stored as a Secret (never shown).
            </p>
          )}

          {error && (
            <div className="rounded-lg border border-red-400/30 bg-red-400/10 px-3 py-2 text-sm text-red-300">
              {error}
            </div>
          )}

          <div className="mt-1 flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 rounded-xl border border-white/10 bg-white/5 py-2.5 text-sm font-semibold text-white/70 transition hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              disabled={!nameValid || busy}
              onClick={() => {
                const options: Record<string, unknown> = { version, storageSize };
                if (game.sizing) options.maxPlayers = maxPlayers;
                onSubmit({ name, game: game.id, options });
              }}
              className="flex-1 rounded-xl py-2.5 text-sm font-semibold text-ink-950 transition active:scale-[0.98] disabled:opacity-40"
              style={{ background: `linear-gradient(135deg, ${game.accent}, ${game.accent}cc)` }}
            >
              {busy ? "Deploying…" : "Deploy server"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
