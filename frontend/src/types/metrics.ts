export interface ServerMetrics {
  name: string;
  cpuPercent: number | null; // of pod CPU limit (null => unavailable)
  memoryPercent: number | null; // of pod memory limit (null => unavailable)
  diskPercent: number | null; // PVC used/capacity (null => unavailable)
  cpuMilli?: number | null;
  memoryMiB?: number | null;
}

export interface ClusterHealth {
  cluster: string;
  nodesReady: number;
  nodesTotal: number;
  podsRunning: number;
  podsError: number;
  serversDesired: number;
  serversReady: number;
  problems: string[];
}
