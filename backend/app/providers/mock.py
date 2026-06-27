"""In-memory mock of the Kubernetes layer.

Simulates the GameServer lifecycle the real operator would drive:
    Pending -> Provisioning -> Running  (then Stopping on delete)
Phase is derived from elapsed time so it advances on its own with no background
worker to manage, and the frontend's polling sees a realistic progression.

An RCON password is generated per server and kept server-side only — never returned
in the API and never logged (mirrors the real Secret hygiene requirement).
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone

from .. import catalog
from ..models import (
    CreateServerRequest,
    GameServer,
    GameServerSpec,
    GameServerStatus,
)
from .base import Provider

# Snappy but realistic-looking demo timings (seconds since creation).
_PENDING_UNTIL = 2.0
_PROVISIONING_UNTIL = 7.0

# Stable pretend node IP (what ServiceLB/Klipper would assign as EXTERNAL-IP).
_NODE_IP = "192.168.127.2"


class _Record:
    __slots__ = ("server", "created_monotonic", "rcon_password", "deleting_since")

    def __init__(self, server: GameServer, rcon_password: str):
        self.server = server
        self.created_monotonic = time.monotonic()
        self.rcon_password = rcon_password  # never serialized out
        self.deleting_since: float | None = None


class MockProvider(Provider):
    def __init__(self) -> None:
        self._records: dict[str, _Record] = {}

    def _primary_port(self, game_id: str) -> int:
        g = catalog.get_game(game_id)
        if g and g.get("ports"):
            return g["ports"][0]["port"]
        return 0

    def _refresh(self, rec: _Record) -> GameServer:
        """Recompute phase/address/ready from elapsed time."""
        srv = rec.server
        if rec.deleting_since is not None:
            srv.status.phase = "Stopping"
            srv.status.ready = False
            srv.status.message = "Terminating: saving world and stopping container"
            return srv

        age = time.monotonic() - rec.created_monotonic
        if age < _PENDING_UNTIL:
            srv.status.phase = "Pending"
            srv.status.ready = False
            srv.status.address = None
            srv.status.message = "Scheduling StatefulSet"
        elif age < _PROVISIONING_UNTIL:
            srv.status.phase = "Provisioning"
            srv.status.ready = False
            srv.status.address = None
            srv.status.podName = f"{srv.name}-0"
            srv.status.message = "Pulling image and starting container"
        else:
            srv.status.phase = "Running"
            srv.status.ready = True
            srv.status.podName = f"{srv.name}-0"
            port = self._primary_port(srv.spec.game)
            srv.status.address = f"{_NODE_IP}:{port}"
            srv.status.message = "Server is live"
        return srv

    async def list_servers(self) -> list[GameServer]:
        return [self._refresh(r) for r in self._records.values()]

    async def get_server(self, name: str) -> GameServer | None:
        rec = self._records.get(name)
        return self._refresh(rec) if rec else None

    async def create_server(self, req: CreateServerRequest) -> GameServer:
        if req.name in self._records:
            raise ValueError(f"server '{req.name}' already exists")
        game = catalog.get_game(req.game)
        if not game:
            raise ValueError(f"unknown game '{req.game}'")

        opts = req.options or {}
        version = opts.get("version") or catalog.default_version(req.game)
        env = dict(game.get("defaultEnv", {}))
        env.update(opts.get("env", {}))

        spec = GameServerSpec(
            game=req.game,
            version=version,
            image=opts.get("image") or game["image"],
            storageSize=opts.get("storageSize", "2Gi"),
            env=env,
            rconEnabled=bool(game.get("rcon", {}).get("enabled", False)),
        )
        server = GameServer(
            name=req.name,
            spec=spec,
            status=GameServerStatus(phase="Pending", message="Accepted"),
            createdAt=datetime.now(timezone.utc).isoformat(),
        )
        rec = _Record(server, rcon_password=secrets.token_urlsafe(18))
        self._records[req.name] = rec
        return self._refresh(rec)

    async def delete_server(self, name: str) -> bool:
        rec = self._records.get(name)
        if not rec:
            return False
        # Simulate graceful stop, then remove shortly after.
        if rec.deleting_since is None:
            rec.deleting_since = time.monotonic()
        # In the mock we remove immediately after marking Stopping so the UI
        # reflects deletion; the real operator GC's via owner references.
        del self._records[name]
        return True
