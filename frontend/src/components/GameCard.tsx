import type { Game } from "../types";

export function GameCard({ game, onDeploy }: { game: Game; onDeploy: (g: Game) => void }) {
  return (
    <div
      className="card-lift fade-in group relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03]"
      style={{ boxShadow: "0 10px 30px -18px rgba(0,0,0,0.8)" }}
    >
      {/* art header: accent gradient + giant glyph */}
      <div
        className="relative flex h-32 items-center justify-center overflow-hidden"
        style={{
          background: `radial-gradient(120% 120% at 50% 0%, ${game.accent}55, transparent 60%), linear-gradient(160deg, ${game.accent}33, rgba(255,255,255,0.02))`,
        }}
      >
        <span className="text-6xl drop-shadow-lg transition-transform duration-300 group-hover:scale-110">
          {game.icon}
        </span>
        <span
          className="absolute right-3 top-3 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
          style={{ color: game.accent, background: "rgba(0,0,0,0.35)" }}
        >
          {game.protocol}
        </span>
      </div>

      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-white">{game.name}</h3>
          <span className="text-xs text-white/40">{game.versions.length} versions</span>
        </div>
        <p className="min-h-[2.5rem] text-sm leading-snug text-white/55">{game.description}</p>
        <button
          onClick={() => onDeploy(game)}
          className="mt-1 w-full rounded-xl py-2.5 text-sm font-semibold text-ink-950 transition active:scale-[0.98]"
          style={{ background: `linear-gradient(135deg, ${game.accent}, ${game.accent}cc)` }}
        >
          Deploy
        </button>
      </div>
    </div>
  );
}
