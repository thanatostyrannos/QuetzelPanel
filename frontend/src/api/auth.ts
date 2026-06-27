// Auth client (SEED — WP-A expands: real login response, token storage, logout).
import type { User } from "../types";
import { http } from "./http";

export const authApi = {
  me: () =>
    http<{ userId: string; username: string; role: string; customerId: string | null }>(
      "/auth/me"
    ),
  // WP-A: returns a JWT to store + send via setAuthToken.
  login: (username: string, password: string) =>
    http<{ token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
};
