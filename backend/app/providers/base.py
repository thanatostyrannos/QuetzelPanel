"""Provider interface — the swap point between the mock layer and the real cluster.

The backend never talks to Kubernetes directly; it talks to a Provider. Today
`QUETZEL_PROVIDER=mock` uses the in-memory MockProvider. Once the k3s cluster is
healthy, `QUETZEL_PROVIDER=k8s` swaps in K8sProvider (creates GameServer CRs) with
zero change to the routes or the frontend.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import CreateServerRequest, GameServer


class Provider(ABC):
    @abstractmethod
    async def list_servers(self) -> list[GameServer]:
        ...

    @abstractmethod
    async def get_server(self, name: str) -> GameServer | None:
        ...

    @abstractmethod
    async def create_server(self, req: CreateServerRequest) -> GameServer:
        ...

    @abstractmethod
    async def delete_server(self, name: str) -> bool:
        ...

    async def startup(self) -> None:  # optional hook
        ...

    async def shutdown(self) -> None:  # optional hook
        ...

    def kind(self) -> str:
        return self.__class__.__name__
