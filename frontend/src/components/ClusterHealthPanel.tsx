/**
 * ClusterHealthPanel — cluster-wide status: nodes, pods, servers desired/ready,
 * and a scrollable problems list.
 *
 * Polls `GET /cluster/health` every `pollMs` milliseconds.
 */
import { useEffect, useState } from "react";
import { metricsApi } from "../api/metrics";
import type { ClusterHealth } from "../types/metrics";

interface ClusterHealthPanelProps {
  pollMs?: number;
}

interface StatBadgeProps {
  label: string;
  ok: number;
  total: number;
  color?: string;
}

function StatBadge({ label, ok, total, color = "#2dd4a7" }: StatBadgeProps) {
  const healthy = ok === total && total > 0;
  const badgeColor = healthy ? color : ok < total ? "#fbbf24" : color;
  return (
    <div
      className="flex flex-col items-center gap-0.5 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2 min-w-[72px]"
      data-testid="stat-badge"
    >
      <span className="text-base font-black" style={{ color: badgeColor }}>
        {ok}/{total}
      </span>
      <span className="text-[10px] text-white/40">{label}</span>
    </div>
  );
}

export function ClusterHealthPanel({ pollMs = 10000 }: ClusterHealthPanelProps) {
  const [health, setHealth] = useState<ClusterHealth | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetch = async () => {
      try {
        const h = await metricsApi.clusterHealth();
        if (!cancelled) {
          setHealth(h);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to fetch cluster health");
        }
      }
    };

    fetch();
    const interval = setInterval(fetch, pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollMs]);

  const allOk =
    health != null &&
    health.nodesReady === health.nodesTotal &&
    health.nodesTotal > 0 &&
    health.podsError === 0 &&
    health.problems.length === 0;

  return (
    <div
      className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
      data-testid="cluster-health-panel"
    >
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{
              background: error
                ? "#f87171"
                : health == null
                  ? "#fbbf24"
                  : allOk
                    ? "#2dd4a7"
                    : "#fbbf24",
              boxShadow: "0 0 8px currentColor",
            }}
          />
          <h3 className="text-sm font-bold text-white">
            Cluster Health
            {health && (
              <span className="ml-2 text-xs font-normal text-white/40">
                {health.cluster}
              </span>
            )}
          </h3>
        </div>
        {error && (
          <span className="text-xs text-red-300/70" data-testid="health-error">
            unavailable
          </span>
        )}
      </div>

      {/* Stats row */}
      {health && (
        <div className="mb-3 flex flex-wrap gap-2" data-testid="health-stats">
          <StatBadge label="Nodes" ok={health.nodesReady} total={health.nodesTotal} />
          <StatBadge
            label="Pods running"
            ok={health.podsRunning}
            total={health.podsRunning + health.podsError}
            color="#38bdf8"
          />
          <StatBadge
            label="Servers"
            ok={health.serversReady}
            total={health.serversDesired}
            color="#a78bfa"
          />
        </div>
      )}

      {/* Problems list */}
      {health && health.problems.length > 0 && (
        <div className="max-h-28 overflow-y-auto rounded-lg border border-red-400/20 bg-red-400/5 px-3 py-2">
          <ul className="space-y-0.5" data-testid="problems-list">
            {health.problems.map((p, i) => (
              <li key={i} className="text-xs text-red-300/80">
                {p}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* All OK banner */}
      {health && health.problems.length === 0 && !error && (
        <div
          className="rounded-lg border border-brand-500/20 bg-brand-500/5 px-3 py-1.5 text-xs text-brand-300"
          data-testid="all-ok-banner"
        >
          All systems nominal
        </div>
      )}

      {/* Loading */}
      {health == null && !error && (
        <div className="text-xs text-white/30" data-testid="health-loading">
          Loading cluster health…
        </div>
      )}
    </div>
  );
}
