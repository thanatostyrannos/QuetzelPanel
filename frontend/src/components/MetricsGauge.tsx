/**
 * MetricsGauge — a single arc-style usage gauge (CPU / Memory / Disk).
 *
 * Props:
 *   label       – display label ("CPU", "Memory", "Disk")
 *   value       – current percentage (0–100), null while loading
 *   color       – accent colour (defaults to brand teal)
 *   subtitle    – optional raw-value string shown below the ring ("256 MiB")
 */
export interface MetricsGaugeProps {
  label: string;
  value: number | null;
  color?: string;
  subtitle?: string;
}

const RADIUS = 28;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function arc(pct: number): number {
  return CIRCUMFERENCE * (1 - Math.min(Math.max(pct, 0), 100) / 100);
}

function levelColor(pct: number, accent: string): string {
  if (pct >= 90) return "#f87171"; // red
  if (pct >= 75) return "#fbbf24"; // amber
  return accent;
}

export function MetricsGauge({ label, value, color = "#2dd4a7", subtitle }: MetricsGaugeProps) {
  const resolved = value ?? 0;
  const strokeColor = value != null ? levelColor(resolved, color) : "#ffffff20";
  const dash = value != null ? arc(resolved) : CIRCUMFERENCE; // full ring when loading

  return (
    <div className="flex flex-col items-center gap-1" data-testid="metrics-gauge">
      {/* SVG ring */}
      <svg width="72" height="72" viewBox="0 0 72 72" aria-hidden="true">
        {/* Track */}
        <circle
          cx="36"
          cy="36"
          r={RADIUS}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth="6"
        />
        {/* Progress arc — starts at top */}
        <circle
          cx="36"
          cy="36"
          r={RADIUS}
          fill="none"
          stroke={strokeColor}
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dash}
          transform="rotate(-90 36 36)"
          style={{ transition: "stroke-dashoffset 0.5s ease, stroke 0.3s ease" }}
        />
        {/* Centre label */}
        <text
          x="36"
          y="40"
          textAnchor="middle"
          fontSize="13"
          fontWeight="700"
          fill={value != null ? strokeColor : "rgba(255,255,255,0.25)"}
          data-testid="gauge-value"
        >
          {value != null ? `${resolved.toFixed(0)}%` : "—"}
        </text>
      </svg>

      {/* Labels */}
      <span className="text-xs font-semibold text-white/70">{label}</span>
      {subtitle && <span className="text-[10px] text-white/35">{subtitle}</span>}
    </div>
  );
}
