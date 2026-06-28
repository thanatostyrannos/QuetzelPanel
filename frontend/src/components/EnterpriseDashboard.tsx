/**
 * EnterpriseDashboard — WP-D
 *
 * Cross-cluster, multi-tenant view for platform-admins.
 * Shows:
 *   - All registered clusters with health badges and a cluster switcher
 *   - Per-cluster server list (tenancy-filtered for customer-users)
 *   - Customer list with drill-down to their cross-cluster server inventory
 *
 * SEAM REQUEST: App.tsx (lead-owned) should import and mount this component:
 *   import { EnterpriseDashboard } from "./components/EnterpriseDashboard";
 *   // Add a nav toggle in the header so admins can switch between
 *   // "My Servers" (existing ServerCard view) and "Enterprise".
 *   // Suggested placement: a tab bar or button row immediately below the
 *   // branded header, visible only when user.role === "platform-admin".
 *   // Example:
 *   //   {user?.role === "platform-admin" && (
 *   //     <EnterpriseDashboard />
 *   //   )}
 */
import { useCallback, useEffect, useState } from "react";
import type { ClusterHealth, ClusterRef, Customer, GameServer } from "../types";
import { clustersApi } from "../api/clusters";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface ClusterBadgeProps {
  cluster: ClusterRef;
  selected: boolean;
  onClick: () => void;
  health: ClusterHealth | null;
}

function ClusterBadge({ cluster, selected, onClick, health }: ClusterBadgeProps) {
  const healthy = health !== null && health.nodesReady === health.nodesTotal && health.problems.length === 0;
  const dot = health === null ? "bg-gray-400" : healthy ? "bg-green-400" : "bg-amber-400";
  return (
    <button
      data-testid={`cluster-badge-${cluster.id}`}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors
        ${selected
          ? "bg-emerald-700 border-emerald-500 text-white"
          : "bg-gray-800 border-gray-600 text-gray-300 hover:bg-gray-700"
        }`}
    >
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      {cluster.name}
      {cluster.local && (
        <span className="ml-1 text-xs text-gray-400">(local)</span>
      )}
    </button>
  );
}

interface ServerRowProps {
  server: GameServer;
}

function ServerRow({ server }: ServerRowProps) {
  const phaseColor: Record<string, string> = {
    Running: "text-green-400",
    Pending: "text-amber-400",
    Provisioning: "text-blue-400",
    Stopping: "text-gray-400",
    Error: "text-red-400",
  };
  const color = phaseColor[server.status.phase] ?? "text-gray-400";
  const customer = (server.spec as { customer?: string }).customer;

  return (
    <tr
      data-testid={`server-row-${server.name}`}
      className="border-t border-gray-700 hover:bg-gray-700/30"
    >
      <td className="py-2 px-3 font-mono text-sm text-white">{server.name}</td>
      <td className="py-2 px-3 text-sm text-gray-300">{server.spec.game}</td>
      <td className={`py-2 px-3 text-sm font-semibold ${color}`}>{server.status.phase}</td>
      <td className="py-2 px-3 text-sm text-gray-400">{customer ?? "—"}</td>
      <td className="py-2 px-3 font-mono text-xs text-gray-400">
        {server.status.address ?? "—"}
      </td>
    </tr>
  );
}

interface CustomerRowProps {
  customer: Customer;
  onSelect: (id: string) => void;
  selected: boolean;
}

function CustomerRow({ customer, onSelect, selected }: CustomerRowProps) {
  return (
    <tr
      data-testid={`customer-row-${customer.id}`}
      className={`border-t border-gray-700 cursor-pointer transition-colors
        ${selected ? "bg-emerald-900/30" : "hover:bg-gray-700/30"}`}
      onClick={() => onSelect(customer.id)}
    >
      <td className="py-2 px-3 text-sm font-medium text-white">{customer.name}</td>
      <td className="py-2 px-3 font-mono text-xs text-gray-400">{customer.id}</td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export function EnterpriseDashboard() {
  const [clusters, setClusters] = useState<ClusterRef[]>([]);
  const [healths, setHealths] = useState<Record<string, ClusterHealth>>({});
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [clusterServers, setClusterServers] = useState<GameServer[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<string | null>(null);
  const [customerServers, setCustomerServers] = useState<GameServer[]>([]);
  const [loadingServers, setLoadingServers] = useState(false);
  const [loadingCustServers, setLoadingCustServers] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load clusters once on mount
  useEffect(() => {
    clustersApi.clusters()
      .then(cs => {
        setClusters(cs);
        if (cs.length > 0) setSelectedCluster(cs[0].id);
      })
      .catch(e => setError(String(e)));
  }, []);

  // Load health for each cluster using the cluster-specific health endpoint
  useEffect(() => {
    clusters.forEach(c => {
      clustersApi.clusterHealth(c.id)
        .then(h => setHealths(prev => ({ ...prev, [c.id]: h })))
        .catch(() => {/* health unavailable */});
    });
  }, [clusters]);

  // Load customers
  useEffect(() => {
    clustersApi.customers()
      .then(setCustomers)
      .catch(e => setError(String(e)));
  }, []);

  // Load servers for the selected cluster
  useEffect(() => {
    if (!selectedCluster) return;
    setLoadingServers(true);
    clustersApi.clusterServers(selectedCluster)
      .then(s => setClusterServers(s))
      .catch(e => setError(String(e)))
      .finally(() => setLoadingServers(false));
  }, [selectedCluster]);

  // Load servers for the selected customer (cross-cluster)
  const selectCustomer = useCallback((id: string) => {
    setSelectedCustomer(id);
    setLoadingCustServers(true);
    clustersApi.customerServers(id)
      .then(setCustomerServers)
      .catch(e => setError(String(e)))
      .finally(() => setLoadingCustServers(false));
  }, []);

  return (
    <div data-testid="enterprise-dashboard" className="p-6 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Enterprise Dashboard</h1>
        <p className="text-gray-400 text-sm mt-1">
          Cross-cluster view — {clusters.length} cluster{clusters.length !== 1 ? "s" : ""} registered
        </p>
      </div>

      {error && (
        <div data-testid="dashboard-error" className="bg-red-900/40 border border-red-700 rounded-lg p-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Cluster Switcher */}
      <section data-testid="cluster-switcher">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Clusters</h2>
        <div className="flex flex-wrap gap-2">
          {clusters.map(c => (
            <ClusterBadge
              key={c.id}
              cluster={c}
              selected={selectedCluster === c.id}
              health={healths[c.id] ?? null}
              onClick={() => setSelectedCluster(c.id)}
            />
          ))}
          {clusters.length === 0 && (
            <p className="text-gray-500 text-sm">No clusters registered.</p>
          )}
        </div>
      </section>

      {/* Cluster Servers */}
      {selectedCluster && (
        <section data-testid="cluster-servers-section">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Servers — {clusters.find(c => c.id === selectedCluster)?.name ?? selectedCluster}
          </h2>
          {loadingServers ? (
            <p data-testid="cluster-servers-loading" className="text-gray-500 text-sm">Loading…</p>
          ) : clusterServers.length === 0 ? (
            <p className="text-gray-500 text-sm">No servers on this cluster.</p>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-700">
              <table className="w-full text-left" data-testid="cluster-servers-table">
                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                  <tr>
                    <th className="py-2 px-3">Name</th>
                    <th className="py-2 px-3">Game</th>
                    <th className="py-2 px-3">Phase</th>
                    <th className="py-2 px-3">Customer</th>
                    <th className="py-2 px-3">Address</th>
                  </tr>
                </thead>
                <tbody>
                  {clusterServers.map(s => <ServerRow key={s.name} server={s} />)}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* Customer List + Drill-down */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <section data-testid="customer-list-section">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Customers ({customers.length})
          </h2>
          {customers.length === 0 ? (
            <p className="text-gray-500 text-sm">No customers yet.</p>
          ) : (
            <div className="rounded-lg border border-gray-700 overflow-hidden">
              <table className="w-full text-left" data-testid="customers-table">
                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                  <tr>
                    <th className="py-2 px-3">Name</th>
                    <th className="py-2 px-3">ID</th>
                  </tr>
                </thead>
                <tbody>
                  {customers.map(c => (
                    <CustomerRow
                      key={c.id}
                      customer={c}
                      selected={selectedCustomer === c.id}
                      onSelect={selectCustomer}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Customer Server Drill-down */}
        {selectedCustomer && (
          <section data-testid="customer-servers-section">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              {customers.find(c => c.id === selectedCustomer)?.name ?? selectedCustomer} — Servers (all clusters)
            </h2>
            {loadingCustServers ? (
              <p data-testid="customer-servers-loading" className="text-gray-500 text-sm">Loading…</p>
            ) : customerServers.length === 0 ? (
              <p className="text-gray-500 text-sm">No servers for this customer.</p>
            ) : (
              <div className="rounded-lg border border-gray-700 overflow-hidden">
                <table className="w-full text-left" data-testid="customer-servers-table">
                  <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                    <tr>
                      <th className="py-2 px-3">Name</th>
                      <th className="py-2 px-3">Game</th>
                      <th className="py-2 px-3">Phase</th>
                      <th className="py-2 px-3">Address</th>
                    </tr>
                  </thead>
                  <tbody>
                    {customerServers.map(s => <ServerRow key={s.name} server={s} />)}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
