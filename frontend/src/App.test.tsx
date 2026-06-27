import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { api } from "./api";
import type { Game, GameServer } from "./types";

vi.mock("./api", () => ({
  api: {
    health: vi.fn(),
    games: vi.fn(),
    servers: vi.fn(),
    getServer: vi.fn(),
    createServer: vi.fn(),
    deleteServer: vi.fn(),
  },
}));

const GAMES: Game[] = [
  {
    id: "minecraft",
    name: "Minecraft",
    description: "Java server",
    image: "itzg/minecraft-server:latest",
    protocol: "tcp",
    ports: [{ name: "game", port: 25565, protocol: "TCP" }],
    rcon: { enabled: true, port: 25575 },
    versions: ["1.21.1"],
    defaultEnv: { EULA: "TRUE" },
    accent: "#5b8c3e",
    icon: "⛏️",
  },
  {
    id: "valheim",
    name: "Valheim",
    description: "Viking server",
    image: "lloesche/valheim-server:latest",
    protocol: "udp",
    ports: [{ name: "game", port: 2456, protocol: "UDP" }],
    rcon: { enabled: false, port: 0 },
    versions: ["stable"],
    defaultEnv: {},
    accent: "#3b6ea5",
    icon: "🛡️",
  },
];

let serverState: GameServer[] = [];

function runningServer(name: string): GameServer {
  return {
    name,
    spec: {
      game: "minecraft",
      version: "1.21.1",
      image: "itzg/minecraft-server:latest",
      resources: { cpu: "1", mem: "2Gi" },
      storageSize: "2Gi",
      env: {},
      rconEnabled: true,
    },
    status: { phase: "Running", address: "192.168.127.2:25565", podName: `${name}-0`, ready: true, message: "Server is live" },
    createdAt: new Date().toISOString(),
  };
}

beforeEach(() => {
  serverState = [];
  vi.mocked(api.health).mockResolvedValue({ status: "ok", provider: "MockProvider" });
  vi.mocked(api.games).mockResolvedValue(GAMES);
  vi.mocked(api.servers).mockImplementation(async () => serverState);
  vi.mocked(api.createServer).mockImplementation(async ({ name }) => {
    const s = runningServer(name);
    serverState = [...serverState, s];
    return s;
  });
  vi.mocked(api.deleteServer).mockImplementation(async (name: string) => {
    serverState = serverState.filter((s) => s.name !== name);
  });
});

describe("App", () => {
  it("renders the catalog and provider badge", async () => {
    render(<App />);
    expect(await screen.findByText("Minecraft")).toBeInTheDocument();
    expect(screen.getByText("Valheim")).toBeInTheDocument();
    expect(await screen.findByText("MockProvider")).toBeInTheDocument();
    expect(await screen.findByText("API online")).toBeInTheDocument();
  });

  it("deploys a server then deletes it end-to-end", async () => {
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText("Minecraft");

    // open Minecraft's deploy modal (first card)
    await user.click(screen.getAllByRole("button", { name: "Deploy" })[0]);
    const input = await screen.findByPlaceholderText("my-server");
    await user.clear(input);
    await user.type(input, "mc-it");
    await user.click(screen.getByRole("button", { name: /deploy server/i }));

    expect(api.createServer).toHaveBeenCalledWith({
      name: "mc-it",
      game: "minecraft",
      options: { version: "1.21.1", storageSize: "2Gi" },
    });

    // appears in My Servers as Running with its address
    expect(await screen.findByText("mc-it")).toBeInTheDocument();
    expect(await screen.findByText("192.168.127.2:25565")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();

    // delete it
    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    expect(api.deleteServer).toHaveBeenCalledWith("mc-it");
    await waitFor(() => expect(screen.queryByText("mc-it")).not.toBeInTheDocument());
  });

  it("shows empty state when there are no servers", async () => {
    render(<App />);
    expect(await screen.findByText(/No servers yet/i)).toBeInTheDocument();
  });
});
