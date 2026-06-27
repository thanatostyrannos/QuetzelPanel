"""API + domain models shared across providers.

These mirror the GameServer CRD (spec/status) so the mock and the real k8s provider
present an identical shape to the frontend.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Phase = Literal["Pending", "Provisioning", "Running", "Stopping", "Error"]


class Resources(BaseModel):
    cpu: str = "1"
    mem: str = "2Gi"


class GameServerSpec(BaseModel):
    game: str
    version: Optional[str] = None
    image: Optional[str] = None           # optional override of catalog image
    resources: Resources = Field(default_factory=Resources)
    storageSize: str = "2Gi"
    env: dict[str, str] = Field(default_factory=dict)
    rconEnabled: bool = True


class GameServerStatus(BaseModel):
    phase: Phase = "Pending"
    address: Optional[str] = None
    podName: Optional[str] = None
    ready: bool = False
    message: str = ""


class GameServer(BaseModel):
    """A deployed game server, as the API returns it."""
    name: str
    spec: GameServerSpec
    status: GameServerStatus = Field(default_factory=GameServerStatus)
    createdAt: Optional[str] = None


class CreateServerRequest(BaseModel):
    name: str
    game: str
    options: dict = Field(default_factory=dict)  # {version, storageSize, env, ...}

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        import re

        v = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]{0,30}[a-z0-9])?", v):
            raise ValueError(
                "name must be a DNS-1123 label: lowercase alphanumerics and '-', "
                "1-32 chars, start/end alphanumeric"
            )
        return v
