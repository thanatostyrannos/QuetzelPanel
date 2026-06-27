"""Comprehensive tests for compute_resources (WP-B: player-based game sizing).

Covers:
  - Basic formula: base + per-player * N (no ceilings)
  - Ceiling clamping (memory and CPU independently)
  - max_players clamping (input > sizing.maxPlayers is clamped)
  - Zero players (base values)
  - Monotonicity (resources are non-decreasing in max_players)
  - Output units: memory ends in "Mi", cpu ends in "m"
  - requests == limits (Guaranteed QoS)
  - build_statefulset integration: sizing used when explicit resources absent
  - build_statefulset: explicit resources always override sizing
  - build_statefulset: no sizing block -> default cpu=1/mem=2Gi
  - playersEnv propagation in _container_env for Minecraft
"""
import pytest

from quetzel_operator import manifests as m

NS = "quetzel"

# Sizing dict matching the contract (same shape as catalog entry's "sizing" block)
SIZING = {
    "baseMemoryMiB": 512,
    "memoryPerPlayerMiB": 10,
    "baseCpuMilli": 250,
    "cpuPerPlayerMilli": 5,
    "maxPlayers": 50,
    "ceilingMemoryMiB": 4096,
    "ceilingCpuMilli": 2000,
}

# No-ceiling sizing for testing unclamped growth
SIZING_NO_CEILING = {
    "baseMemoryMiB": 512,
    "memoryPerPlayerMiB": 10,
    "baseCpuMilli": 250,
    "cpuPerPlayerMilli": 5,
    "maxPlayers": 200,
}

# Catalog-like game entries
MC_GAME = {
    "id": "minecraft",
    "image": "itzg/minecraft-server:latest",
    "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
    "rcon": {"enabled": True, "port": 25575, "passwordEnv": "RCON_PASSWORD", "enableEnv": "ENABLE_RCON"},
    "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
    "versionEnv": "VERSION",
    "dataPath": "/data",
    "stopCommand": "rcon-cli save-all && rcon-cli stop",
    "playersEnv": "MAX_PLAYERS",
    "sizing": SIZING,
}

MC_GAME_NO_SIZING = {
    "id": "minecraft",
    "image": "itzg/minecraft-server:latest",
    "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
    "rcon": {"enabled": True, "port": 25575, "passwordEnv": "RCON_PASSWORD", "enableEnv": "ENABLE_RCON"},
    "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
    "versionEnv": "VERSION",
    "dataPath": "/data",
    "stopCommand": "rcon-cli save-all && rcon-cli stop",
}


# ---------------------------------------------------------------------------
# compute_resources: basic formula
# ---------------------------------------------------------------------------

def test_compute_resources_basic_formula():
    """memory = base + per_player * N; cpu = base + per_player * N (no clamp)."""
    r = m.compute_resources(SIZING_NO_CEILING, 10)
    expected_mem = 512 + 10 * 10   # 612 MiB
    expected_cpu = 250 + 5 * 10    # 300 milli
    assert r["requests"]["memory"] == f"{expected_mem}Mi"
    assert r["requests"]["cpu"] == f"{expected_cpu}m"


def test_compute_resources_zero_players():
    """Zero players yields the base values."""
    r = m.compute_resources(SIZING_NO_CEILING, 0)
    assert r["requests"]["memory"] == "512Mi"
    assert r["requests"]["cpu"] == "250m"


def test_compute_resources_output_units():
    """Memory must end in 'Mi', CPU must end in 'm'."""
    r = m.compute_resources(SIZING, 10)
    assert r["requests"]["memory"].endswith("Mi")
    assert r["requests"]["cpu"].endswith("m")
    assert r["limits"]["memory"].endswith("Mi")
    assert r["limits"]["cpu"].endswith("m")


def test_compute_resources_requests_equal_limits():
    """requests == limits (Guaranteed QoS class)."""
    r = m.compute_resources(SIZING, 20)
    assert r["requests"] == r["limits"]


def test_compute_resources_returns_both_keys():
    """Result has exactly 'requests' and 'limits', each with 'cpu' and 'memory'."""
    r = m.compute_resources(SIZING, 10)
    assert set(r.keys()) == {"requests", "limits"}
    for tier in ("requests", "limits"):
        assert "cpu" in r[tier]
        assert "memory" in r[tier]


# ---------------------------------------------------------------------------
# Ceiling clamping
# ---------------------------------------------------------------------------

def test_compute_resources_memory_ceiling_clamps():
    """When formula exceeds ceilingMemoryMiB the result is capped."""
    # SIZING: base=512, per_player=10, ceiling=4096; at 400 players -> 4512 > 4096
    r = m.compute_resources(SIZING, 400)  # clamped by maxPlayers first to 50
    # at 50: 512 + 10*50 = 1012 < 4096 — not clamped yet
    assert int(r["requests"]["memory"][:-2]) == 1012

    # Use a low-ceiling sizing to force clamp
    low_ceiling = {**SIZING_NO_CEILING, "ceilingMemoryMiB": 600}
    r2 = m.compute_resources(low_ceiling, 20)  # formula = 512 + 10*20 = 712 > 600
    assert int(r2["requests"]["memory"][:-2]) == 600


def test_compute_resources_cpu_ceiling_clamps():
    """When cpu formula exceeds ceilingCpuMilli the result is capped."""
    low_cpu_ceiling = {**SIZING_NO_CEILING, "ceilingCpuMilli": 300}
    # formula: 250 + 5*20 = 350 > 300
    r = m.compute_resources(low_cpu_ceiling, 20)
    assert int(r["requests"]["cpu"][:-1]) == 300


def test_compute_resources_ceiling_none_means_no_clamp():
    """When ceiling fields are absent the values grow without limit."""
    r = m.compute_resources(SIZING_NO_CEILING, 100)
    expected_mem = 512 + 10 * 100  # 1512
    assert int(r["requests"]["memory"][:-2]) == expected_mem


# ---------------------------------------------------------------------------
# max_players clamping
# ---------------------------------------------------------------------------

def test_compute_resources_maxplayers_input_clamped():
    """Input max_players > sizing.maxPlayers is clamped to sizing.maxPlayers."""
    r_max = m.compute_resources(SIZING, 50)   # exactly sizing.maxPlayers
    r_over = m.compute_resources(SIZING, 999)  # way over
    assert r_max["requests"] == r_over["requests"]


def test_compute_resources_negative_maxplayers_clamped_to_zero():
    """Negative max_players is clamped to 0 (never subtract from base)."""
    r = m.compute_resources(SIZING_NO_CEILING, -5)
    r0 = m.compute_resources(SIZING_NO_CEILING, 0)
    assert r["requests"] == r0["requests"]


# ---------------------------------------------------------------------------
# Monotonicity
# ---------------------------------------------------------------------------

def test_compute_resources_monotone_memory():
    """More players never produces less memory."""
    prev_mem = 0
    for n in (0, 1, 5, 10, 20, 40, 50, 100):
        r = m.compute_resources(SIZING, n)
        mem = int(r["requests"]["memory"][:-2])
        assert mem >= prev_mem, f"non-monotone at n={n}"
        prev_mem = mem


def test_compute_resources_monotone_cpu():
    """More players never produces less CPU."""
    prev_cpu = 0
    for n in (0, 1, 5, 10, 20, 40, 50, 100):
        r = m.compute_resources(SIZING, n)
        cpu = int(r["requests"]["cpu"][:-1])
        assert cpu >= prev_cpu, f"non-monotone at n={n}"
        prev_cpu = cpu


# ---------------------------------------------------------------------------
# Invalid sizing input
# ---------------------------------------------------------------------------

def test_compute_resources_rejects_negative_base():
    """Negative baseMemoryMiB or baseCpuMilli must raise ValueError."""
    bad = {**SIZING_NO_CEILING, "baseMemoryMiB": -1}
    with pytest.raises((ValueError, AssertionError)):
        m.compute_resources(bad, 10)


# ---------------------------------------------------------------------------
# build_statefulset integration: player-based sizing
# ---------------------------------------------------------------------------

SPEC_WITH_MAXPLAYERS = {
    "game": "minecraft",
    "version": "1.21.1",
    "image": None,
    "resources": {},          # absent / empty -> sizing should kick in
    "storageSize": "2Gi",
    "env": {},
    "rconEnabled": True,
    "maxPlayers": 20,
}

SPEC_WITH_EXPLICIT_RESOURCES = {
    "game": "minecraft",
    "version": "1.21.1",
    "image": None,
    "resources": {"cpu": "4", "mem": "8Gi"},
    "storageSize": "2Gi",
    "env": {},
    "rconEnabled": True,
    "maxPlayers": 20,
}

SPEC_NO_SIZING = {
    "game": "minecraft",
    "version": "1.21.1",
    "image": None,
    "resources": {},
    "storageSize": "2Gi",
    "env": {},
    "rconEnabled": True,
}


def test_build_statefulset_uses_sizing_when_no_explicit_resources():
    """Empty resources + maxPlayers + game has sizing -> compute_resources output."""
    expected = m.compute_resources(SIZING, 20)
    ss = m.build_statefulset("mc1", NS, SPEC_WITH_MAXPLAYERS, MC_GAME)
    c_res = ss["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert c_res["requests"]["memory"] == expected["requests"]["memory"]
    assert c_res["requests"]["cpu"] == expected["requests"]["cpu"]
    assert c_res["limits"] == c_res["requests"]


def test_build_statefulset_explicit_resources_override_sizing():
    """Explicit resources always win, even when maxPlayers and sizing are set."""
    ss = m.build_statefulset("mc1", NS, SPEC_WITH_EXPLICIT_RESOURCES, MC_GAME)
    c_res = ss["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert c_res["requests"]["cpu"] == "4"
    assert c_res["requests"]["memory"] == "8Gi"


def test_build_statefulset_defaults_when_no_sizing_no_resources():
    """No sizing block and no explicit resources -> defaults (cpu=1, mem=2Gi)."""
    ss = m.build_statefulset("mc1", NS, SPEC_NO_SIZING, MC_GAME_NO_SIZING)
    c_res = ss["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert c_res["requests"]["cpu"] == "1"
    assert c_res["requests"]["memory"] == "2Gi"


def test_build_statefulset_defaults_when_no_maxplayers():
    """Sizing block present but no maxPlayers -> defaults (no player count to size)."""
    spec = {**SPEC_WITH_MAXPLAYERS, "maxPlayers": None}
    ss = m.build_statefulset("mc1", NS, spec, MC_GAME)
    c_res = ss["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert c_res["requests"]["cpu"] == "1"
    assert c_res["requests"]["memory"] == "2Gi"


# ---------------------------------------------------------------------------
# playersEnv propagation
# ---------------------------------------------------------------------------

def test_container_env_sets_players_env_when_configured():
    """When game has playersEnv and spec has maxPlayers, the env var is set."""
    spec = {
        "game": "minecraft",
        "version": "1.21.1",
        "env": {},
        "rconEnabled": False,
        "maxPlayers": 30,
    }
    env_list = m._container_env(spec, MC_GAME, "mc1")
    env_map = {e["name"]: e.get("value") for e in env_list}
    assert env_map.get("MAX_PLAYERS") == "30"


def test_container_env_omits_players_env_when_no_maxplayers():
    """When maxPlayers is absent/None, MAX_PLAYERS env is not set."""
    spec = {
        "game": "minecraft",
        "version": "1.21.1",
        "env": {},
        "rconEnabled": False,
    }
    env_list = m._container_env(spec, MC_GAME, "mc1")
    names = {e["name"] for e in env_list}
    assert "MAX_PLAYERS" not in names


def test_container_env_no_players_env_key_in_game():
    """When game doesn't have playersEnv, no MAX_PLAYERS env is added."""
    spec = {
        "game": "minecraft",
        "version": "1.21.1",
        "env": {},
        "rconEnabled": False,
        "maxPlayers": 30,
    }
    env_list = m._container_env(spec, MC_GAME_NO_SIZING, "mc1")
    names = {e["name"] for e in env_list}
    assert "MAX_PLAYERS" not in names
