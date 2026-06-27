import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "./index";

function mockFetch(impl: (url: string) => { json?: () => Promise<unknown>; status?: number; ok?: boolean }) {
  return vi.fn(async (url: string) => {
    const r = impl(url);
    return {
      ok: r.ok ?? true,
      status: r.status ?? 200,
      statusText: "OK",
      json: r.json ?? (async () => ({})),
    } as Response;
  });
}

describe("extended api contracts (auth/metrics/clusters/customers)", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("me() hits /auth/me", async () => {
    const f = mockFetch(() => ({ json: async () => ({ userId: "dev", username: "dev", role: "platform-admin", customerId: null }) }));
    vi.stubGlobal("fetch", f);
    const me = await api.me();
    expect(f).toHaveBeenCalledWith("/api/auth/me", expect.anything());
    expect(me.role).toBe("platform-admin");
  });

  it("serverMetrics() hits /servers/:name/metrics", async () => {
    const f = mockFetch(() => ({ json: async () => ({ name: "mc", cpuPercent: 12, memoryPercent: 34, diskPercent: 5 }) }));
    vi.stubGlobal("fetch", f);
    const m = await api.serverMetrics("mc");
    expect(f).toHaveBeenCalledWith("/api/servers/mc/metrics", expect.anything());
    expect(m.memoryPercent).toBe(34);
  });

  it("clusters() + customerServers() hit the right paths", async () => {
    const f = mockFetch((url) =>
      url.endsWith("/clusters")
        ? { json: async () => [{ id: "local", name: "local", local: true }] }
        : { json: async () => [] }
    );
    vi.stubGlobal("fetch", f);
    const c = await api.clusters();
    expect(c[0].id).toBe("local");
    await api.customerServers("cust-a");
    expect(f).toHaveBeenCalledWith("/api/customers/cust-a/servers", expect.anything());
  });
});
