import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  const onLogin = vi.fn();

  beforeEach(() => {
    onLogin.mockReset();
  });

  it("renders username and password fields", () => {
    render(<LoginPage onLogin={onLogin} />);
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls onLogin with credentials when submitted", async () => {
    const user = userEvent.setup();
    onLogin.mockResolvedValue(undefined);
    render(<LoginPage onLogin={onLogin} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "s3cret!");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(onLogin).toHaveBeenCalledWith("alice", "s3cret!");
  });

  it("shows error message on failed login", async () => {
    const user = userEvent.setup();
    onLogin.mockRejectedValue(new Error("invalid credentials"));
    render(<LoginPage onLogin={onLogin} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/invalid credentials/i);
  });

  it("disables submit button while loading", async () => {
    const user = userEvent.setup();
    // onLogin never resolves during this test
    let resolve!: () => void;
    onLogin.mockReturnValue(new Promise<void>((r) => { resolve = r; }));
    render(<LoginPage onLogin={onLogin} />);

    await user.type(screen.getByLabelText(/username/i), "alice");
    await user.type(screen.getByLabelText(/password/i), "pw");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("button", { name: /signing in/i })).toBeDisabled();
    resolve();
  });

  it("shows Google sign-in button", () => {
    render(<LoginPage onLogin={onLogin} />);
    expect(screen.getByRole("link", { name: /google/i })).toBeInTheDocument();
  });
});
