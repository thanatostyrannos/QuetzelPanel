"""Contract tests for the sizing schema (model + catalog)."""
from app import catalog
from app.models import GameServerSpec, Sizing


def test_sizing_model_optional_ceilings():
    s = Sizing(
        baseMemoryMiB=512,
        memoryPerPlayerMiB=10,
        baseCpuMilli=250,
        cpuPerPlayerMilli=5,
        maxPlayers=50,
    )
    assert s.ceilingMemoryMiB is None and s.ceilingCpuMilli is None


def test_spec_carries_maxplayers_and_customer():
    spec = GameServerSpec(game="minecraft", maxPlayers=8, customer="cust-a")
    assert spec.maxPlayers == 8 and spec.customer == "cust-a"


def test_every_catalog_game_has_sizing():
    required = ("baseMemoryMiB", "memoryPerPlayerMiB", "baseCpuMilli", "cpuPerPlayerMilli", "maxPlayers")
    for g in catalog.list_games():
        assert "sizing" in g, f"{g['id']} missing sizing"
        for k in required:
            assert k in g["sizing"], f"{g['id']}.sizing missing {k}"
