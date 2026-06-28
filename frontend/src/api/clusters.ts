// Multi-cluster + tenancy client (WP-D: switcher, rollups, cross-cluster server views).
import type { ClusterHealth, ClusterRef, Customer, GameServer } from "../types";
import { http } from "./http";

export const clustersApi = {
  /** List all registered clusters. */
  clusters: () => http<ClusterRef[]>("/clusters"),

  /** Health of a single cluster. */
  clusterHealth: (id: string) => http<ClusterHealth>(`/clusters/${id}/health`),

  /** All servers on a specific cluster (tenancy-filtered). */
  clusterServers: (id: string) => http<GameServer[]>(`/clusters/${id}/servers`),

  /** Cross-cluster server rollup (admin: all; customer: own scope). */
  rollupServers: () => http<GameServer[]>("/clusters/rollup/servers"),

  /** All customers (platform-admin: all; customer-user: own). */
  customers: () => http<Customer[]>("/customers"),

  /** Servers for one customer, merged across all clusters. */
  customerServers: (id: string) => http<GameServer[]>(`/customers/${id}/servers`),
};
