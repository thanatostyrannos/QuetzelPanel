// Composed API surface. Feature clients live in sibling files
// (servers, games, and — added by the WPs — auth, metrics, clusters).
import { http } from "./http";
import { gamesApi } from "./games";
import { serversApi } from "./servers";
import { authApi } from "./auth";
import { metricsApi } from "./metrics";
import { clustersApi } from "./clusters";

export { http, BASE, setAuthToken, getAuthToken } from "./http";

export const api = {
  health: () => http<{ status: string; provider: string }>("/healthz"),
  ...gamesApi,
  ...serversApi,
  ...authApi,
  ...metricsApi,
  ...clustersApi,
};
