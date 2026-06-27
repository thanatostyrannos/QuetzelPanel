"""Game catalog — the single declarative source of which games QuetzelPanel can deploy.

Adding a game = adding an entry here (or to a mounted ConfigMap that overrides this).
No code change required elsewhere: the operator, backend API and frontend all read this.

Each entry:
  id            stable key used in the GameServer spec.game enum
  name          display name
  description   short blurb for the card
  image         container image the operator runs (StatefulSet)
  protocol      tcp | udp  (informational; drives Service port protocol)
  ports         list of {name, port, protocol} the Service exposes
  rcon          {enabled, port} if the game supports RCON-style admin
  versions      selectable versions for the Deploy form (first = default)
  defaultEnv    env vars always set (e.g. EULA acceptance, shown explicitly)
  accent        UI accent color (hex) for the card
  icon          emoji used as lightweight card art (no external assets needed)
"""
from __future__ import annotations

CATALOG: list[dict] = [
    {
        "id": "minecraft",
        "name": "Minecraft",
        "description": "Java Edition survival/creative server (itzg).",
        "image": "itzg/minecraft-server:latest",
        # Player-based sizing. The memory LIMIT must comfortably exceed the JVM
        # heap (+ Paper/JVM non-heap overhead) or the pod OOM-CrashLoops. Base
        # 1536Mi leaves ~500Mi headroom over a ~1G heap; per-player widens tiers.
        "sizing": {
            "baseMemoryMiB": 1536,
            "memoryPerPlayerMiB": 128,
            "baseCpuMilli": 500,
            "cpuPerPlayerMilli": 125,
            "maxPlayers": 50,
            "ceilingMemoryMiB": 8192,
            "ceilingCpuMilli": 4000,
        },
        "protocol": "tcp",
        "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
        # rcon: passwordEnv/enableEnv tell the operator how to inject the
        # generated Secret + enable RCON for THIS image (data-driven, no code).
        "rcon": {
            "enabled": True,
            "port": 25575,
            "passwordEnv": "RCON_PASSWORD",
            "enableEnv": "ENABLE_RCON",
        },
        "versions": ["1.21.1", "1.20.6", "1.20.4", "1.19.4"],
        "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
        "versionEnv": "VERSION",            # version goes to env, not image tag
        "playersEnv": "MAX_PLAYERS",        # WP-B: operator sets this from spec.maxPlayers
        "dataPath": "/data",                # world volume mount
        "stopCommand": "rcon-cli save-all && rcon-cli stop",  # graceful preStop
        "accent": "#5b8c3e",
        "icon": "⛏️",  # pickaxe
    },
    {
        "id": "valheim",
        "name": "Valheim",
        "description": "Co-op Viking survival dedicated server (lloesche).",
        "image": "lloesche/valheim-server:latest",
        "sizing": {
            "baseMemoryMiB": 1536,
            "memoryPerPlayerMiB": 64,
            "baseCpuMilli": 500,
            "cpuPerPlayerMilli": 50,
            "maxPlayers": 10,
            "ceilingMemoryMiB": 4096,
            "ceilingCpuMilli": 3000,
        },
        "protocol": "udp",
        "ports": [
            {"name": "game", "port": 2456, "protocol": "UDP"},
            {"name": "query", "port": 2457, "protocol": "UDP"},
        ],
        "rcon": {"enabled": False, "port": 0},
        "versions": ["stable", "public-test"],
        "defaultEnv": {"SERVER_NAME": "QuetzelPanel Valheim", "WORLD_NAME": "Midgard"},
        "dataPath": "/config",
        "accent": "#3b6ea5",
        "icon": "\U0001f6e1️",  # shield
    },
    {
        "id": "terraria",
        "name": "Terraria",
        "description": "2D sandbox adventure dedicated server.",
        "image": "ryshe/terraria:latest",
        "sizing": {
            "baseMemoryMiB": 512,
            "memoryPerPlayerMiB": 8,
            "baseCpuMilli": 200,
            "cpuPerPlayerMilli": 3,
            "maxPlayers": 16,
            "ceilingMemoryMiB": 2048,
            "ceilingCpuMilli": 1500,
        },
        "protocol": "tcp",
        "ports": [{"name": "game", "port": 7777, "protocol": "TCP"}],
        "rcon": {"enabled": False, "port": 0},
        "versions": ["latest", "1.4.4.9"],
        "defaultEnv": {"WORLD_SIZE": "2", "DIFFICULTY": "1"},
        "dataPath": "/root/.local/share/Terraria/Worlds",
        "accent": "#9b6bce",
        "icon": "\U0001f333",  # tree
    },
    {
        "id": "factorio",
        "name": "Factorio",
        "description": "Automation & logistics multiplayer server.",
        "image": "factoriotools/factorio:stable",
        "sizing": {
            "baseMemoryMiB": 1024,
            "memoryPerPlayerMiB": 16,
            "baseCpuMilli": 300,
            "cpuPerPlayerMilli": 8,
            "maxPlayers": 64,
            "ceilingMemoryMiB": 4096,
            "ceilingCpuMilli": 3000,
        },
        "protocol": "udp",
        "ports": [{"name": "game", "port": 34197, "protocol": "UDP"}],
        "rcon": {
            "enabled": True,
            "port": 27015,
            "passwordEnv": "RCON_PASSWORD",
        },
        "versions": ["stable", "latest"],
        "defaultEnv": {},
        "dataPath": "/factorio",
        "accent": "#d98a29",
        "icon": "⚙️",  # gear
    },
]

_BY_ID = {g["id"]: g for g in CATALOG}


def list_games() -> list[dict]:
    return CATALOG


def get_game(game_id: str) -> dict | None:
    return _BY_ID.get(game_id)


def default_version(game_id: str) -> str | None:
    g = _BY_ID.get(game_id)
    return g["versions"][0] if g and g.get("versions") else None
