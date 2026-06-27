import type { Game } from "../types";
import { http } from "./http";

export const gamesApi = {
  games: () => http<{ games: Game[] }>("/games").then((r) => r.games),
};
