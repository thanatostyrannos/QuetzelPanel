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
        "protocol": "tcp",
        "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
        "rcon": {"enabled": True, "port": 25575},
        "versions": ["1.21.1", "1.20.6", "1.20.4", "1.19.4"],
        "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
        "accent": "#5b8c3e",
        "icon": "⛏️",  # pickaxe
    },
    {
        "id": "valheim",
        "name": "Valheim",
        "description": "Co-op Viking survival dedicated server (lloesche).",
        "image": "lloesche/valheim-server:latest",
        "protocol": "udp",
        "ports": [
            {"name": "game", "port": 2456, "protocol": "UDP"},
            {"name": "query", "port": 2457, "protocol": "UDP"},
        ],
        "rcon": {"enabled": False, "port": 0},
        "versions": ["stable", "public-test"],
        "defaultEnv": {"SERVER_NAME": "QuetzelPanel Valheim", "WORLD_NAME": "Midgard"},
        "accent": "#3b6ea5",
        "icon": "\U0001f6e1️",  # shield
    },
    {
        "id": "terraria",
        "name": "Terraria",
        "description": "2D sandbox adventure dedicated server.",
        "image": "ryshe/terraria:latest",
        "protocol": "tcp",
        "ports": [{"name": "game", "port": 7777, "protocol": "TCP"}],
        "rcon": {"enabled": False, "port": 0},
        "versions": ["latest", "1.4.4.9"],
        "defaultEnv": {"WORLD_SIZE": "2", "DIFFICULTY": "1"},
        "accent": "#9b6bce",
        "icon": "\U0001f333",  # tree
    },
    {
        "id": "factorio",
        "name": "Factorio",
        "description": "Automation & logistics multiplayer server.",
        "image": "factoriotools/factorio:stable",
        "protocol": "udp",
        "ports": [{"name": "game", "port": 34197, "protocol": "UDP"}],
        "rcon": {"enabled": True, "port": 27015},
        "versions": ["stable", "latest"],
        "defaultEnv": {},
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
