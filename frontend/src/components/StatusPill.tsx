import type { Phase } from "../types";

const STYLES: Record<Phase, { label: string; color: string; bg: string; pulse: boolean }> = {
  Pending: { label: "Pending", color: "#fbbf24", bg: "rgba(251,191,36,0.12)", pulse: true },
  Provisioning: { label: "Provisioning", color: "#38bdf8", bg: "rgba(56,189,248,0.12)", pulse: true },
  Running: { label: "Running", color: "#2dd4a7", bg: "rgba(45,212,167,0.14)", pulse: false },
  Stopping: { label: "Stopping", color: "#fb923c", bg: "rgba(251,146,60,0.14)", pulse: true },
  Error: { label: "Error", color: "#f87171", bg: "rgba(248,113,113,0.14)", pulse: false },
};

export function StatusPill({ phase }: { phase: Phase }) {
  const s = STYLES[phase];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold"
      style={{ color: s.color, background: s.bg, border: `1px solid ${s.color}33` }}
    >
      <span
        className={"h-2 w-2 rounded-full " + (s.pulse ? "dot-pulse" : "")}
        style={{ background: s.color, boxShadow: `0 0 8px ${s.color}` }}
      />
      {s.label}
    </span>
  );
}
