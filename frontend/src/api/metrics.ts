// Observability client (SEED — WP-C expands: polling, gauges).
import type { ClusterHealth, ServerMetrics } from "../types";
import { http } from "./http";

export const metricsApi = {
  serverMetrics: (name: string) => http<ServerMetrics>(`/servers/${name}/metrics`),
  clusterHealth: () => http<ClusterHealth>("/cluster/health"),
};
