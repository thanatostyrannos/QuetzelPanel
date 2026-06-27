import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAuth } from "./useAuth";
import { setAuthToken } from "../api";

// Partial mock of ../api: keep real setAuthToken, mock api object
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    api: {
      login: vi.fn(),
      me: vi.fn(),
    },
  };
});

import { api } from "../api";

describe("useAuth", () => {
  beforeEach(() => {
    localStorage.clear();
    setAuthToken(null);
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    setAuthToken(null);
  });

  it("starts unauthenticated with no stored token", () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("login() stores token and sets user", async () => {
    const mockUser = { id: "u1", username: "alice", role: "customer-user" as const, customerId: "acme" };
    vi.mocked(api.login).mockResolvedValue({ token: "tok123", user: mockUser });

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.login("alice", "pw");
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe("alice");
    expect(localStorage.getItem("quetzel_token")).toBe("tok123");
  });

  it("logout() clears token and user", async () => {
    const mockUser = { id: "u1", username: "alice", role: "customer-user" as const, customerId: "acme" };
    vi.mocked(api.login).mockResolvedValue({ token: "tok123", user: mockUser });

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.login("alice", "pw");
    });

    act(() => {
      result.current.logout();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(localStorage.getItem("quetzel_token")).toBeNull();
  });

  it("restores session from localStorage on mount", async () => {
    localStorage.setItem("quetzel_token", "stored-tok");
    vi.mocked(api.me).mockResolvedValue({ userId: "u1", username: "alice", role: "customer-user", customerId: "acme" });

    const { result } = renderHook(() => useAuth());

    // Wait for the async restore to complete
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.username).toBe("alice");
  });

  it("clears bad stored token if /me fails", async () => {
    localStorage.setItem("quetzel_token", "bad-token");
    vi.mocked(api.me).mockRejectedValue(new Error("401 Unauthorized"));

    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(localStorage.getItem("quetzel_token")).toBeNull();
  });
});
