export type Phase =
  | "Pending"
  | "Provisioning"
  | "Running"
  | "Stopping"
  | "Error";

export interface Port {
  name: string;
  port: number;
  protocol: string;
}

export interface Game {
  id: string;
  name: string;
  description: string;
  image: string;
  protocol: string;
  ports: Port[];
  rcon: { enabled: boolean; port: number };
  versions: string[];
  defaultEnv: Record<string, string>;
  accent: string;
  icon: string;
}

export interface GameServerStatus {
  phase: Phase;
  address: string | null;
  podName: string | null;
  ready: boolean;
  message: string;
}

export interface GameServerSpec {
  game: string;
  version: string | null;
  image: string | null;
  resources: { cpu: string; mem: string };
  storageSize: string;
  env: Record<string, string>;
  rconEnabled: boolean;
}

export interface GameServer {
  name: string;
  spec: GameServerSpec;
  status: GameServerStatus;
  createdAt: string | null;
}
