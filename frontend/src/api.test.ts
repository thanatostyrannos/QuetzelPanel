import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "./api";

function mockFetch(impl: (url: string, init?: RequestInit) => Partial<Response> & { json?: () => Promise<unknown> }) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const r = impl(url, init);
    return {
      ok: r.ok ?? true,
      status: r.status ?? 200,
      statusText: r.statusText ?? "OK",
      json: r.json ?? (async () => ({})),
    } as Response;
  });
}

describe("api client", () => {
  beforeEach(() => vi.restoreAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it("games() hits /api/games and unwraps {games}", async () => {
    const f = mockFetch(() => ({ json: async () => ({ games: [{ id: "minecraft" }] }) }));
    vi.stubGlobal("fetch", f);
    const games = await api.games();
    expect(f).toHaveBeenCalledWith("/api/games", expect.anything());
    expect(games[0].id).toBe("minecraft");
  });

  it("createServer() POSTs JSON body", async () => {
    const f = mockFetch(() => ({ status: 201, json: async () => ({ name: "mc" }) }));
    vi.stubGlobal("fetch", f);
    await api.createServer({ name: "mc", game: "minecraft", options: { version: "1.21.1" } });
    const [, init] = f.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toMatchObject({ name: "mc", game: "minecraft" });
  });

  it("deleteServer() handles 204 with no body", async () => {
    const f = mockFetch(() => ({ status: 204 }));
    vi.stubGlobal("fetch", f);
    await expect(api.deleteServer("mc")).resolves.toBeUndefined();
  });

  it("surfaces backend `detail` message on error", async () => {
    const f = mockFetch(() => ({
      ok: false,
      status: 409,
      statusText: "Conflict",
      json: async () => ({ detail: "server 'mc' already exists" }),
    }));
    vi.stubGlobal("fetch", f);
    await expect(api.createServer({ name: "mc", game: "minecraft", options: {} })).rejects.toThrow(
      "server 'mc' already exists"
    );
  });
});
