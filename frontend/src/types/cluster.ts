export interface ClusterRef {
  id: string;
  name: string;
  local: boolean;
}

/** Cross-cluster rollup entry for the enterprise dashboard. */
export interface ClusterRollup {
  cluster: ClusterRef;
  health: import("./metrics").ClusterHealth | null;
  serverCount: number;
  runningCount: number;
}
