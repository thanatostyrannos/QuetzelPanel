import type { Game, GameServer } from "./types";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => http<{ status: string; provider: string }>("/healthz"),
  games: () => http<{ games: Game[] }>("/games").then((r) => r.games),
  servers: () => http<GameServer[]>("/servers"),
  getServer: (name: string) => http<GameServer>(`/servers/${name}`),
  createServer: (payload: {
    name: string;
    game: string;
    options: Record<string, unknown>;
  }) =>
    http<GameServer>("/servers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteServer: (name: string) =>
    http<void>(`/servers/${name}`, { method: "DELETE" }),
};
