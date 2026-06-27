"""Contract test pinning compute_resources (implemented by WP-B / player-sizing).

xfail (non-strict) so Phase 0 CI is green while the stub raises NotImplementedError;
flips to a real pass once WP-B lands the math, at which point the marker is removed.
"""
import pytest

from quetzel_operator import manifests


@pytest.mark.xfail(reason="compute_resources implemented in WP-B (player-sizing)", strict=False)
def test_compute_resources_contract():
    sizing = {
        "baseMemoryMiB": 512,
        "memoryPerPlayerMiB": 10,
        "baseCpuMilli": 250,
        "cpuPerPlayerMilli": 5,
        "maxPlayers": 50,
        "ceilingMemoryMiB": 4096,
        "ceilingCpuMilli": 2000,
    }
    r = manifests.compute_resources(sizing, 10)
    assert "requests" in r and "limits" in r
    assert r["requests"]["memory"].endswith("Mi")
    assert r["requests"]["cpu"].endswith("m")
    # monotonic: more players -> at least as much memory
    bigger = manifests.compute_resources(sizing, 40)
    assert int(bigger["requests"]["memory"][:-2]) >= int(r["requests"]["memory"][:-2])
