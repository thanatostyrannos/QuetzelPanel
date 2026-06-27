// Multi-cluster + tenancy client (SEED — WP-D expands: switcher, rollups).
import type { ClusterHealth, ClusterRef, Customer, GameServer } from "../types";
import { http } from "./http";

export const clustersApi = {
  clusters: () => http<ClusterRef[]>("/clusters"),
  clusterHealth: (id: string) => http<ClusterHealth>(`/clusters/${id}/health`),
  customers: () => http<Customer[]>("/customers"),
  customerServers: (id: string) => http<GameServer[]>(`/customers/${id}/servers`),
};
