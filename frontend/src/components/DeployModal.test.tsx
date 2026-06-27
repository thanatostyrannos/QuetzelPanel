import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DeployModal } from "./DeployModal";
import type { Game } from "../types";

const MINECRAFT: Game = {
  id: "minecraft",
  name: "Minecraft",
  description: "Java server",
  image: "itzg/minecraft-server:latest",
  protocol: "tcp",
  ports: [{ name: "game", port: 25565, protocol: "TCP" }],
  rcon: { enabled: true, port: 25575 },
  versions: ["1.21.1", "1.20.6"],
  defaultEnv: { EULA: "TRUE" },
  accent: "#5b8c3e",
  icon: "⛏️",
};

function setup(overrides: Partial<Parameters<typeof DeployModal>[0]> = {}) {
  const onSubmit = vi.fn();
  const onClose = vi.fn();
  render(
    <DeployModal
      game={MINECRAFT}
      busy={false}
      error={null}
      onClose={onClose}
      onSubmit={onSubmit}
      {...overrides}
    />
  );
  return { onSubmit, onClose };
}

describe("DeployModal", () => {
  it("renders the game and shows the explicit EULA notice for Minecraft", () => {
    setup();
    expect(screen.getByText("Deploy Minecraft")).toBeInTheDocument();
    expect(screen.getByText(/accept the Minecraft EULA/i)).toBeInTheDocument();
  });

  it("disables Deploy when the name is invalid", async () => {
    const user = userEvent.setup();
    setup();
    const input = screen.getByPlaceholderText("my-server");
    await user.clear(input);
    await user.type(input, "Bad Name!");
    expect(screen.getByText(/lowercase letters, digits and dashes/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deploy server/i })).toBeDisabled();
  });

  it("submits the expected payload for a valid name", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();
    const input = screen.getByPlaceholderText("my-server");
    await user.clear(input);
    await user.type(input, "my-mc");
    await user.click(screen.getByRole("button", { name: /deploy server/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      name: "my-mc",
      game: "minecraft",
      options: { version: "1.21.1", storageSize: "2Gi" },
    });
  });

  it("calls onClose from Cancel", async () => {
    const user = userEvent.setup();
    const { onClose } = setup();
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});
