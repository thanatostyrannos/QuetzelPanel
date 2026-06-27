// Auth client — WP-A implementation.
import type { User } from "../types";
import { http } from "./http";

export const authApi = {
  me: () =>
    http<{ userId: string; username: string; role: string; customerId: string | null }>(
      "/auth/me"
    ),
  // Returns a JWT to store + send via setAuthToken.
  login: (username: string, password: string) =>
    http<{ token: string; user: User }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  // Stateless logout: clears server-side session (always succeeds).
  logout: () =>
    http<{ detail: string }>("/auth/logout", { method: "POST" }),
};
