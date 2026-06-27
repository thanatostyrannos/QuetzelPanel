import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DeployModal } from "./DeployModal";
import type { Game, Sizing } from "../types";

const MC_SIZING: Sizing = {
  baseMemoryMiB: 768,
  memoryPerPlayerMiB: 12,
  baseCpuMilli: 250,
  cpuPerPlayerMilli: 5,
  maxPlayers: 50,
  ceilingMemoryMiB: 4096,
  ceilingCpuMilli: 2000,
};

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
  sizing: MC_SIZING,
};

/** A game with no sizing block (should not show the max-players control). */
const NO_SIZING_GAME: Game = {
  ...MINECRAFT,
  id: "valheim",
  name: "Valheim",
  sizing: undefined,
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

describe("DeployModal — existing behaviour", () => {
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

  it("submits the expected payload for a valid name (includes maxPlayers when sizing present)", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();
    const input = screen.getByPlaceholderText("my-server");
    await user.clear(input);
    await user.type(input, "my-mc");
    await user.click(screen.getByRole("button", { name: /deploy server/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      name: "my-mc",
      game: "minecraft",
      options: { version: "1.21.1", storageSize: "2Gi", maxPlayers: 50 },
    });
  });

  it("calls onClose from Cancel", async () => {
    const user = userEvent.setup();
    const { onClose } = setup();
    await user.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("DeployModal — WP-B: max-players + resource preview", () => {
  it("shows the max-players input when game has sizing", () => {
    setup();
    expect(screen.getByLabelText(/max players/i)).toBeInTheDocument();
  });

  it("does NOT show the max-players input when game has no sizing", () => {
    setup({ game: NO_SIZING_GAME });
    expect(screen.queryByLabelText(/max players/i)).not.toBeInTheDocument();
  });

  it("defaults to sizing.maxPlayers", () => {
    setup();
    const input = screen.getByLabelText(/max players/i) as HTMLInputElement;
    expect(input.value).toBe("50");
  });

  it("shows a resource preview panel", () => {
    setup();
    expect(screen.getByLabelText(/resource preview/i)).toBeInTheDocument();
  });

  it("resource preview updates when player count changes", () => {
    setup();
    const input = screen.getByLabelText(/max players/i);
    // Use fireEvent.change for reliable number input updates
    fireEvent.change(input, { target: { value: "10" } });
    // 768 + 12*10 = 888 MiB; 250 + 5*10 = 300 mCPU
    expect(screen.getByText("888 MiB")).toBeInTheDocument();
    expect(screen.getByText("300 mCPU")).toBeInTheDocument();
  });

  it("preview matches computeResources formula at default maxPlayers (50 players)", () => {
    setup();
    // 768 + 12*50 = 1368 MiB; 250 + 5*50 = 500 mCPU
    expect(screen.getByText("1368 MiB")).toBeInTheDocument();
    expect(screen.getByText("500 mCPU")).toBeInTheDocument();
  });

  it("includes maxPlayers in submitted options", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup();
    const playerInput = screen.getByLabelText(/max players/i);
    fireEvent.change(playerInput, { target: { value: "20" } });
    const nameInput = screen.getByPlaceholderText("my-server");
    await user.clear(nameInput);
    await user.type(nameInput, "mc-small");
    await user.click(screen.getByRole("button", { name: /deploy server/i }));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({ maxPlayers: 20 }),
      })
    );
  });

  it("omits maxPlayers from options when game has no sizing", async () => {
    const user = userEvent.setup();
    const { onSubmit } = setup({ game: NO_SIZING_GAME });
    const nameInput = screen.getByPlaceholderText("my-server");
    await user.clear(nameInput);
    await user.type(nameInput, "v-srv");
    await user.click(screen.getByRole("button", { name: /deploy server/i }));
    const call = onSubmit.mock.calls[0][0];
    expect(call.options.maxPlayers).toBeUndefined();
  });
});
