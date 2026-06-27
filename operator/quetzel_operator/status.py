"""Pure helpers that derive GameServer status from observed cluster objects.

Kept dependency-free and unit-tested so the reconciliation decision logic is
verified offline; handlers.py just feeds in what the k8s API returns.
"""
from __future__ import annotations


def service_address(svc: dict, port: int) -> str | None:
    """Return 'host:port' once ServiceLB assigns an ingress IP/hostname, else None."""
    ingress = (
        (svc or {}).get("status", {}).get("loadBalancer", {}).get("ingress") or []
    )
    if not ingress:
        return None
    host = ingress[0].get("ip") or ingress[0].get("hostname")
    return f"{host}:{port}" if host else None


def compute_phase(
    *,
    deleting: bool,
    statefulset_exists: bool,
    ready_replicas: int,
    address: str | None,
) -> dict:
    """Map observed state to a GameServer status block."""
    if deleting:
        return {"phase": "Stopping", "ready": False, "address": address,
                "message": "Terminating: saving world and stopping container"}
    if not statefulset_exists:
        return {"phase": "Pending", "ready": False, "address": None,
                "message": "Scheduling StatefulSet"}
    if ready_replicas >= 1 and address:
        return {"phase": "Running", "ready": True, "address": address,
                "message": "Server is live"}
    return {"phase": "Provisioning", "ready": False, "address": address,
            "message": "Pulling image and starting container"}
