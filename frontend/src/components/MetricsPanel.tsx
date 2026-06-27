/**
 * MetricsPanel — shows CPU / Memory / Disk gauges for a single game server.
 *
 * Polls `GET /servers/:name/metrics` every `pollMs` milliseconds.
 * Renders a compact row of three MetricsGauge rings.
 */
import { useEffect, useState } from "react";
import { metricsApi } from "../api/metrics";
import type { ServerMetrics } from "../types/metrics";
import { MetricsGauge } from "./MetricsGauge";

interface MetricsPanelProps {
  serverName: string;
  pollMs?: number;
}

export function MetricsPanel({ serverName, pollMs = 5000 }: MetricsPanelProps) {
  const [metrics, setMetrics] = useState<ServerMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetch = async () => {
      try {
        const m = await metricsApi.serverMetrics(serverName);
        if (!cancelled) {
          setMetrics(m);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to fetch metrics");
        }
      }
    };

    fetch();
    const interval = setInterval(fetch, pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [serverName, pollMs]);

  if (error) {
    return (
      <div
        className="flex items-center gap-1.5 rounded-lg border border-red-400/20 bg-red-400/5 px-3 py-1.5 text-xs text-red-300/70"
        data-testid="metrics-error"
      >
        metrics unavailable
      </div>
    );
  }

  const cpuSub = metrics?.cpuMilli != null ? `${metrics.cpuMilli} m` : undefined;
  const memSub = metrics?.memoryMiB != null ? `${metrics.memoryMiB} MiB` : undefined;

  return (
    <div
      className="flex items-center gap-4 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2"
      data-testid="metrics-panel"
      aria-label={`Metrics for ${serverName}`}
    >
      <MetricsGauge label="CPU" value={metrics?.cpuPercent ?? null} color="#38bdf8" subtitle={cpuSub} />
      <MetricsGauge label="Memory" value={metrics?.memoryPercent ?? null} color="#a78bfa" subtitle={memSub} />
      <MetricsGauge label="Disk" value={metrics?.diskPercent ?? null} color="#2dd4a7" />
    </div>
  );
}
