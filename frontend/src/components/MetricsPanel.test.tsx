import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MetricsPanel } from "./MetricsPanel";
import { MetricsGauge } from "./MetricsGauge";
import { ClusterHealthPanel } from "./ClusterHealthPanel";
import * as metricsModule from "../api/metrics";
import type { ServerMetrics, ClusterHealth } from "../types/metrics";

// ---------------------------------------------------------------------------
// MetricsGauge unit tests
// ---------------------------------------------------------------------------

describe("MetricsGauge", () => {
  it("renders the label", () => {
    render(<MetricsGauge label="CPU" value={42} />);
    expect(screen.getByText("CPU")).toBeInTheDocument();
  });

  it("renders the percentage value", () => {
    render(<MetricsGauge label="Memory" value={75} />);
    expect(screen.getByTestId("gauge-value")).toHaveTextContent("75%");
  });

  it("renders a dash when value is null", () => {
    render(<MetricsGauge label="Disk" value={null} />);
    expect(screen.getByTestId("gauge-value")).toHaveTextContent("—");
  });

  it("renders the subtitle when provided", () => {
    render(<MetricsGauge label="Memory" value={60} subtitle="512 MiB" />);
    expect(screen.getByText("512 MiB")).toBeInTheDocument();
  });

  it("shows three gauges in MetricsPanel", async () => {
    const mockMetrics: ServerMetrics = {
      name: "mc",
      cpuPercent: 20,
      memoryPercent: 45,
      diskPercent: 10,
      cpuMilli: 200,
      memoryMiB: 512,
    };
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockResolvedValue(mockMetrics);

    render(<MetricsPanel serverName="mc" pollMs={9999999} />);
    const gauges = await screen.findAllByTestId("metrics-gauge");
    expect(gauges).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// MetricsPanel
// ---------------------------------------------------------------------------

describe("MetricsPanel", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  const sampleMetrics: ServerMetrics = {
    name: "mc-test",
    cpuPercent: 33,
    memoryPercent: 67,
    diskPercent: 25,
    cpuMilli: 330,
    memoryMiB: 768,
  };

  it("renders the panel container", async () => {
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockResolvedValue(sampleMetrics);
    render(<MetricsPanel serverName="mc-test" pollMs={9999999} />);
    await waitFor(() => expect(screen.getByTestId("metrics-panel")).toBeInTheDocument());
  });

  it("renders CPU, Memory and Disk labels after data loads", async () => {
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockResolvedValue(sampleMetrics);
    render(<MetricsPanel serverName="mc-test" pollMs={9999999} />);
    await screen.findByText("CPU");
    expect(screen.getByText("Memory")).toBeInTheDocument();
    expect(screen.getByText("Disk")).toBeInTheDocument();
  });

  it("shows raw CPU milli subtitle", async () => {
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockResolvedValue(sampleMetrics);
    render(<MetricsPanel serverName="mc-test" pollMs={9999999} />);
    await screen.findByText("330 m");
  });

  it("shows raw memory MiB subtitle", async () => {
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockResolvedValue(sampleMetrics);
    render(<MetricsPanel serverName="mc-test" pollMs={9999999} />);
    await screen.findByText("768 MiB");
  });

  it("shows error state when API throws", async () => {
    vi.spyOn(metricsModule.metricsApi, "serverMetrics").mockRejectedValue(new Error("503"));
    render(<MetricsPanel serverName="mc-test" pollMs={9999999} />);
    await screen.findByTestId("metrics-error");
  });
});

// ---------------------------------------------------------------------------
// ClusterHealthPanel
// ---------------------------------------------------------------------------

describe("ClusterHealthPanel", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  const sampleHealth: ClusterHealth = {
    cluster: "local",
    nodesReady: 1,
    nodesTotal: 1,
    podsRunning: 3,
    podsError: 0,
    serversDesired: 2,
    serversReady: 2,
    problems: [],
  };

  it("renders the panel", async () => {
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(sampleHealth);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await waitFor(() => expect(screen.getByTestId("cluster-health-panel")).toBeInTheDocument());
  });

  it("shows stat badges after data loads", async () => {
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(sampleHealth);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByTestId("health-stats");
    const badges = screen.getAllByTestId("stat-badge");
    expect(badges.length).toBeGreaterThanOrEqual(3);
  });

  it("shows all-ok banner when no problems", async () => {
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(sampleHealth);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByTestId("all-ok-banner");
  });

  it("shows problems list when problems exist", async () => {
    const withProblems: ClusterHealth = {
      ...sampleHealth,
      podsError: 1,
      problems: ["pod/mc-0: CrashLoopBackOff (restarts=7)"],
    };
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(withProblems);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByTestId("problems-list");
    expect(screen.getByText("pod/mc-0: CrashLoopBackOff (restarts=7)")).toBeInTheDocument();
  });

  it("shows cluster name", async () => {
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(sampleHealth);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByText("local");
  });

  it("shows error badge when API fails", async () => {
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockRejectedValue(new Error("503"));
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByTestId("health-error");
  });

  it("shows loading state initially before data resolves", () => {
    // Never resolves during the test
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockReturnValue(new Promise(() => {}));
    render(<ClusterHealthPanel pollMs={9999999} />);
    expect(screen.getByTestId("health-loading")).toBeInTheDocument();
  });

  it("displays nodes ratio correctly", async () => {
    const twoNodes: ClusterHealth = { ...sampleHealth, nodesReady: 1, nodesTotal: 2 };
    vi.spyOn(metricsModule.metricsApi, "clusterHealth").mockResolvedValue(twoNodes);
    render(<ClusterHealthPanel pollMs={9999999} />);
    await screen.findByTestId("health-stats");
    expect(screen.getByText("1/2")).toBeInTheDocument();
  });
});
