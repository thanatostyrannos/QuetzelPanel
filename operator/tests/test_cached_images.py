"""WP-E: operator resolves per-version baked (registry-cached) images and runs
them via TYPE=CUSTOM so pods never download the server jar at runtime."""
from quetzel_operator import manifests


GAME = {
    "id": "minecraft",
    "image": "itzg/minecraft-server:latest",
    "cachedImageRepo": "ghcr.io/acme/quetzel-game-minecraft",
    "cachedServerPath": "/opt/minecraft/server.jar",
    "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
    "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
    "versionEnv": "VERSION",
    "dataPath": "/data",
    "rcon": {"enabled": True, "port": 25575, "passwordEnv": "RCON_PASSWORD", "enableEnv": "ENABLE_RCON"},
}


def _env(ss):
    c = ss["spec"]["template"]["spec"]["containers"][0]
    return {e["name"]: e.get("value") for e in c["env"]}, c["image"]


def test_cached_image_used_for_known_version():
    ss = manifests.build_statefulset("mc", "quetzel", {"game": "minecraft", "version": "1.20.4"}, GAME)
    env, image = _env(ss)
    assert image == "ghcr.io/acme/quetzel-game-minecraft:1.20.4"
    # baked image runs the jar directly; no runtime download/patch
    assert env["TYPE"] == "CUSTOM"
    assert env["CUSTOM_SERVER"] == "/opt/minecraft/server.jar"
    # VERSION env is meaningless for CUSTOM and must not be injected
    assert "VERSION" not in env
    # EULA still flows through
    assert env["EULA"] == "TRUE"


def test_explicit_image_overrides_cache():
    ss = manifests.build_statefulset(
        "mc", "quetzel", {"game": "minecraft", "version": "1.20.4", "image": "custom/mc:dev"}, GAME
    )
    env, image = _env(ss)
    assert image == "custom/mc:dev"
    assert env["TYPE"] == "VANILLA"  # not cached -> catalog default stands


def test_no_version_falls_back_to_catalog_image():
    ss = manifests.build_statefulset("mc", "quetzel", {"game": "minecraft"}, GAME)
    _, image = _env(ss)
    assert image == "itzg/minecraft-server:latest"


def test_game_without_cache_unaffected():
    game = {k: v for k, v in GAME.items() if not k.startswith("cached")}
    ss = manifests.build_statefulset("mc", "quetzel", {"game": "minecraft", "version": "1.20.4"}, game)
    env, image = _env(ss)
    assert image == "itzg/minecraft-server:latest"
    assert env["TYPE"] == "VANILLA"
    assert env["VERSION"] == "1.20.4"
