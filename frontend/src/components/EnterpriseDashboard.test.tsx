/**
 * WP-D: Enterprise Dashboard component tests.
 *
 * Strategy: mock the API clients entirely so no network requests happen.
 * Tests verify:
 *   - Dashboard renders
 *   - Cluster switcher shows registered clusters
 *   - Cluster server list loads and shows servers
 *   - Customer list loads and shows customers
 *   - Customer drill-down fetches cross-cluster servers
 *   - Error states are shown
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";
import { EnterpriseDashboard } from "./EnterpriseDashboard";
import * as clustersModule from "../api/clusters";
import type { ClusterHealth, ClusterRef, Customer, GameServer } from "../types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const LOCAL_CLUSTER: ClusterRef = { id: "local", name: "local", local: true };
const REMOTE_CLUSTER: ClusterRef = { id: "remote-1", name: "mock-remote-1", local: false };

const CUSTOMER_A: Customer = { id: "acme", name: "Acme Corp" };
const CUSTOMER_B: Customer = { id: "globex", name: "Globex" };

const HEALTH: ClusterHealth = {
  cluster: "local",
  nodesReady: 1,
  nodesTotal: 1,
  podsRunning: 2,
  podsError: 0,
  serversDesired: 2,
  serversReady: 2,
  problems: [],
};

function makeServer(name: string, customer: string, phase = "Running"): GameServer {
  return {
    name,
    spec: {
      game: "minecraft",
      version: "1.20.4",
      image: null,
      resources: { cpu: "1", mem: "2Gi" },
      storageSize: "2Gi",
      env: {},
      rconEnabled: false,
      customer,
    } as GameServer["spec"] & { customer: string },
    status: {
      phase: phase as GameServer["status"]["phase"],
      address: phase === "Running" ? "192.168.1.2:25565" : null,
      podName: `${name}-0`,
      ready: phase === "Running",
      message: "Server is live",
    },
    createdAt: "2026-06-27T00:00:00Z",
  };
}

const ACME_SERVER = makeServer("acme-mc1", "acme");
const GLOBEX_SERVER = makeServer("globex-mc1", "globex");
const REMOTE_ACME_SERVER = makeServer("acme-remote-mc1", "acme");

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function mockApis({
  clusters = [LOCAL_CLUSTER],
  health = HEALTH,
  clusterServers = [ACME_SERVER],
  customers = [CUSTOMER_A],
  customerServers = [ACME_SERVER],
}: {
  clusters?: ClusterRef[];
  health?: ClusterHealth | null;
  clusterServers?: GameServer[];
  customers?: Customer[];
  customerServers?: GameServer[];
} = {}) {
  vi.spyOn(clustersModule.clustersApi, "clusters").mockResolvedValue(clusters);
  vi.spyOn(clustersModule.clustersApi, "clusterServers").mockResolvedValue(clusterServers);
  vi.spyOn(clustersModule.clustersApi, "customers").mockResolvedValue(customers);
  vi.spyOn(clustersModule.clustersApi, "customerServers").mockResolvedValue(customerServers);
  vi.spyOn(clustersModule.clustersApi, "rollupServers").mockResolvedValue(clusterServers);
  if (health !== null) {
    vi.spyOn(clustersModule.clustersApi, "clusterHealth").mockResolvedValue(health);
  } else {
    vi.spyOn(clustersModule.clustersApi, "clusterHealth").mockRejectedValue(new Error("unavailable"));
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EnterpriseDashboard", () => {
  it("renders the dashboard container", async () => {
    mockApis();
    render(<EnterpriseDashboard />);
    expect(screen.getByTestId("enterprise-dashboard")).toBeInTheDocument();
  });

  it("shows the cluster count in the heading", async () => {
    mockApis({ clusters: [LOCAL_CLUSTER, REMOTE_CLUSTER] });
    render(<EnterpriseDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/2 cluster/i)).toBeInTheDocument()
    );
  });

  it("renders a badge per cluster", async () => {
    mockApis({ clusters: [LOCAL_CLUSTER, REMOTE_CLUSTER] });
    render(<EnterpriseDashboard />);
    await screen.findByTestId("cluster-badge-local");
    await screen.findByTestId("cluster-badge-remote-1");
  });

  it("marks local cluster with '(local)' annotation", async () => {
    mockApis({ clusters: [LOCAL_CLUSTER] });
    render(<EnterpriseDashboard />);
    await waitFor(() => expect(screen.getByText("(local)")).toBeInTheDocument());
  });

  it("shows cluster servers table after loading", async () => {
    mockApis({ clusterServers: [ACME_SERVER] });
    render(<EnterpriseDashboard />);
    await screen.findByTestId("cluster-servers-table");
    expect(screen.getByTestId("server-row-acme-mc1")).toBeInTheDocument();
  });

  it("shows customer list", async () => {
    mockApis({ customers: [CUSTOMER_A, CUSTOMER_B] });
    render(<EnterpriseDashboard />);
    await screen.findByTestId("customers-table");
    expect(screen.getByTestId("customer-row-acme")).toBeInTheDocument();
    expect(screen.getByTestId("customer-row-globex")).toBeInTheDocument();
  });

  it("drills into customer servers on click", async () => {
    mockApis({
      customers: [CUSTOMER_A],
      // clusterServers shows only the remote server so testids don't collide
      clusterServers: [REMOTE_ACME_SERVER],
      customerServers: [ACME_SERVER, REMOTE_ACME_SERVER],
    });
    render(<EnterpriseDashboard />);
    const custRow = await screen.findByTestId("customer-row-acme");
    fireEvent.click(custRow);
    const custTable = await screen.findByTestId("customer-servers-table");
    // Use within() to scope to the customer servers table
    expect(within(custTable).getByTestId("server-row-acme-mc1")).toBeInTheDocument();
    expect(within(custTable).getByTestId("server-row-acme-remote-mc1")).toBeInTheDocument();
  });

  it("shows empty state when no servers on cluster", async () => {
    mockApis({ clusterServers: [] });
    render(<EnterpriseDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no servers on this cluster/i)).toBeInTheDocument()
    );
  });

  it("shows empty state when no customers", async () => {
    mockApis({ customers: [] });
    render(<EnterpriseDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no customers yet/i)).toBeInTheDocument()
    );
  });

  it("shows error banner when cluster fetch fails", async () => {
    vi.spyOn(clustersModule.clustersApi, "clusters").mockRejectedValue(new Error("network error"));
    vi.spyOn(clustersModule.clustersApi, "customers").mockResolvedValue([]);
    render(<EnterpriseDashboard />);
    await screen.findByTestId("dashboard-error");
  });

  it("shows phase in server rows", async () => {
    const pendingSrv = makeServer("pending-mc", "acme", "Pending");
    mockApis({ clusterServers: [pendingSrv] });
    render(<EnterpriseDashboard />);
    await screen.findByTestId("server-row-pending-mc");
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows customer ID in the customer table", async () => {
    mockApis({ customers: [CUSTOMER_A] });
    render(<EnterpriseDashboard />);
    const table = await screen.findByTestId("customers-table");
    // Use within() to scope to the customers table to avoid ambiguity
    expect(within(table).getByText("acme")).toBeInTheDocument();
  });

  it("shows cluster switcher section", async () => {
    mockApis();
    render(<EnterpriseDashboard />);
    expect(screen.getByTestId("cluster-switcher")).toBeInTheDocument();
  });

  it("shows customer servers loading state", async () => {
    // Never resolves during this test
    vi.spyOn(clustersModule.clustersApi, "clusters").mockResolvedValue([LOCAL_CLUSTER]);
    vi.spyOn(clustersModule.clustersApi, "clusterServers").mockResolvedValue([]);
    vi.spyOn(clustersModule.clustersApi, "customers").mockResolvedValue([CUSTOMER_A]);
    vi.spyOn(clustersModule.clustersApi, "customerServers").mockReturnValue(
      new Promise(() => {})
    );
    vi.spyOn(clustersModule.clustersApi, "clusterHealth").mockResolvedValue(HEALTH);

    render(<EnterpriseDashboard />);
    const custRow = await screen.findByTestId("customer-row-acme");
    fireEvent.click(custRow);
    await screen.findByTestId("customer-servers-loading");
  });
});
