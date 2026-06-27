"""Real Kubernetes provider — creates/reads/deletes GameServer custom resources.

NOT exercised while QUETZEL_PROVIDER=mock (k3s cluster is down per BLOCKERS.md B1),
but written to be correct so it drops in unchanged once the cluster is healthy.
It only touches GameServer CRs in one namespace — the operator does the heavy lifting
of turning a CR into StatefulSet/Service/Secret. This matches the least-privilege RBAC
in charts/quetzel.

The kubernetes client is imported lazily so the mock path needs no k8s dependency.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .. import catalog
from ..models import CreateServerRequest, GameServer, GameServerSpec, GameServerStatus
from .base import Provider

GROUP = "quetzel.gg"
VERSION = "v1alpha1"
PLURAL = "gameservers"


class K8sProvider(Provider):
    def __init__(self, namespace: str | None = None) -> None:
        self.namespace = namespace or os.getenv("QUETZEL_NAMESPACE", "quetzel")
        self._api = None  # CustomObjectsApi

    async def startup(self) -> None:
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        self._api = client.CustomObjectsApi()

    def _to_server(self, obj: dict) -> GameServer:
        spec = obj.get("spec", {})
        status = obj.get("status", {})
        return GameServer(
            name=obj["metadata"]["name"],
            spec=GameServerSpec(
                game=spec.get("game", ""),
                version=spec.get("version"),
                image=spec.get("image"),
                storageSize=spec.get("storageSize", "2Gi"),
                env=spec.get("env", {}),
                rconEnabled=spec.get("rconEnabled", True),
            ),
            status=GameServerStatus(
                phase=status.get("phase", "Pending"),
                address=status.get("address"),
                podName=status.get("podName"),
                ready=status.get("ready", False),
                message=status.get("message", ""),
            ),
            createdAt=obj["metadata"].get("creationTimestamp"),
        )

    async def list_servers(self) -> list[GameServer]:
        resp = self._api.list_namespaced_custom_object(
            GROUP, VERSION, self.namespace, PLURAL
        )
        return [self._to_server(o) for o in resp.get("items", [])]

    async def get_server(self, name: str) -> GameServer | None:
        from kubernetes.client.exceptions import ApiException

        try:
            obj = self._api.get_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, name
            )
        except ApiException as e:
            if e.status == 404:
                return None
            raise
        return self._to_server(obj)

    async def create_server(self, req: CreateServerRequest) -> GameServer:
        game = catalog.get_game(req.game)
        if not game:
            raise ValueError(f"unknown game '{req.game}'")
        opts = req.options or {}
        env = dict(game.get("defaultEnv", {}))
        env.update(opts.get("env", {}))
        body = {
            "apiVersion": f"{GROUP}/{VERSION}",
            "kind": "GameServer",
            "metadata": {"name": req.name, "namespace": self.namespace},
            "spec": {
                "game": req.game,
                "version": opts.get("version") or catalog.default_version(req.game),
                "storageSize": opts.get("storageSize", "2Gi"),
                "env": env,
                "rconEnabled": bool(game.get("rcon", {}).get("enabled", False)),
            },
        }
        obj = self._api.create_namespaced_custom_object(
            GROUP, VERSION, self.namespace, PLURAL, body
        )
        srv = self._to_server(obj)
        srv.createdAt = srv.createdAt or datetime.now(timezone.utc).isoformat()
        return srv

    async def delete_server(self, name: str) -> bool:
        from kubernetes.client.exceptions import ApiException

        try:
            self._api.delete_namespaced_custom_object(
                GROUP, VERSION, self.namespace, PLURAL, name
            )
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise
