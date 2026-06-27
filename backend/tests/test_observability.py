"""Contract tests for the metrics/clusters seams (synthetic mock + endpoints)."""
import asyncio

from app.metrics.provider import SyntheticMetricsProvider
from app.clusters.registry import LocalClusterRegistry


def test_synthetic_metrics_in_range():
    p = SyntheticMetricsProvider()
    m = asyncio.run(p.server_metrics("mc"))
    for v in (m.cpuPercent, m.memoryPercent, m.diskPercent):
        assert 0.0 <= v <= 100.0
    # deterministic per name
    m2 = asyncio.run(p.server_metrics("mc"))
    assert m.cpuPercent == m2.cpuPercent


def test_local_registry():
    r = LocalClusterRegistry()
    assert [c.id for c in r.list_clusters()] == ["local"]
    assert r.get("local").local is True
    assert r.get("nope") is None


def test_metrics_endpoints(client):
    r = client.get("/servers/mc/metrics")
    assert r.status_code == 200
    assert {"cpuPercent", "memoryPercent", "diskPercent"}.issubset(r.json().keys())
    r = client.get("/cluster/health")
    assert r.status_code == 200
    assert r.json()["cluster"] == "local"


def test_clusters_endpoints(client):
    r = client.get("/clusters")
    assert r.status_code == 200
    assert "local" in [c["id"] for c in r.json()]
    assert client.get("/clusters/local/health").status_code == 200
    assert client.get("/clusters/nope/health").status_code == 404
