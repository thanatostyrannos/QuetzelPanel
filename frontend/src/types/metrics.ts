export interface ServerMetrics {
  name: string;
  cpuPercent: number; // of pod CPU limit
  memoryPercent: number; // of pod memory limit
  diskPercent: number; // PVC used/capacity
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
