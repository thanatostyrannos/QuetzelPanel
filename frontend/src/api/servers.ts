import type { GameServer } from "../types";
import { http } from "./http";

export const serversApi = {
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
