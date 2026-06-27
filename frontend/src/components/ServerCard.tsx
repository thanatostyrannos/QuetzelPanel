import { useState } from "react";
import type { Game, GameServer } from "../types";
import { StatusPill } from "./StatusPill";

export function ServerCard({
  server,
  game,
  onDelete,
  deleting,
}: {
  server: GameServer;
  game?: Game;
  onDelete: (name: string) => void;
  deleting: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const addr = server.status.address;

  const copy = async () => {
    if (!addr) return;
    try {
      await navigator.clipboard.writeText(addr);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="fade-in flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div
          className="flex h-11 w-11 items-center justify-center rounded-xl text-2xl"
          style={{ background: `${game?.accent ?? "#2dd4a7"}22` }}
        >
          {game?.icon ?? "🎮"}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white">{server.name}</span>
            <span className="text-xs text-white/40">
              {game?.name ?? server.spec.game} · {server.spec.version ?? "—"}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-white/40">{server.status.message}</div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {addr ? (
          <button
            onClick={copy}
            title="Copy connect address"
            className="group flex items-center gap-2 rounded-lg border border-white/10 bg-ink-800 px-3 py-1.5 font-mono text-xs text-brand-400 transition hover:border-brand-500/50"
          >
            {addr}
            <span className="text-white/30 group-hover:text-white/60">
              {copied ? "✓" : "⧉"}
            </span>
          </button>
        ) : (
          <span className="rounded-lg border border-white/5 bg-ink-800 px-3 py-1.5 font-mono text-xs text-white/30">
            awaiting address…
          </span>
        )}

        <StatusPill phase={server.status.phase} />

        <button
          onClick={() => onDelete(server.name)}
          disabled={deleting}
          className="rounded-lg border border-red-400/20 bg-red-400/5 px-3 py-1.5 text-xs font-semibold text-red-300 transition hover:bg-red-400/15 disabled:opacity-40"
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </div>
    </div>
  );
}
