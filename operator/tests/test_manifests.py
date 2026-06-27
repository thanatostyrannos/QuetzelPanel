"""TDD spec for the operator's pure manifest builders.

These build the StatefulSet / Service / Secret a GameServer reconciles to, with NO
cluster needed — so the reconciliation shape is verified offline while k3s is down.
Written before the implementation (red), then implemented to green.
"""
import pytest

from quetzel_operator import manifests as m

NS = "quetzel"

MC_GAME = {
    "id": "minecraft",
    "image": "itzg/minecraft-server:latest",
    "ports": [{"name": "game", "port": 25565, "protocol": "TCP"}],
    "rcon": {"enabled": True, "port": 25575, "passwordEnv": "RCON_PASSWORD", "enableEnv": "ENABLE_RCON"},
    "defaultEnv": {"EULA": "TRUE", "TYPE": "VANILLA"},
    "versionEnv": "VERSION",
    "dataPath": "/data",
    "stopCommand": "rcon-cli save-all && rcon-cli stop",
}

MC_SPEC = {
    "game": "minecraft",
    "version": "1.21.1",
    "image": None,
    "resources": {"cpu": "1", "mem": "2Gi"},
    "storageSize": "3Gi",
    "env": {"MOTD": "hello"},
    "rconEnabled": True,
}

UDP_GAME = {
    "id": "valheim",
    "image": "lloesche/valheim-server:latest",
    "ports": [
        {"name": "game", "port": 2456, "protocol": "UDP"},
        {"name": "query", "port": 2457, "protocol": "UDP"},
    ],
    "rcon": {"enabled": False, "port": 0},
    "defaultEnv": {"WORLD_NAME": "Midgard"},
    "dataPath": "/config",
}


# --- helpers -----------------------------------------------------------------

def test_generate_rcon_password_is_strong_and_unique():
    a, b = m.generate_rcon_password(), m.generate_rcon_password()
    assert len(a) >= 20 and a != b


def test_labels_include_instance():
    lbl = m.labels("mc1")
    assert lbl["quetzel.gg/server"] == "mc1"
    assert "app.kubernetes.io/instance" in lbl


def test_secret_name_derivation():
    assert m.secret_name("mc1") == "mc1-rcon"


def test_owner_reference_controls_gc():
    ref = m.owner_reference("mc1", "uid-123")
    assert ref["kind"] == "GameServer"
    assert ref["controller"] is True
    assert ref["blockOwnerDeletion"] is True
    assert ref["uid"] == "uid-123"


# --- secret ------------------------------------------------------------------

def test_build_secret_carries_password_in_stringdata():
    s = m.build_secret("mc1", NS, "s3cret-pw")
    assert s["kind"] == "Secret"
    assert s["metadata"]["name"] == "mc1-rcon"
    assert s["metadata"]["namespace"] == NS
    assert s["stringData"]["rcon-password"] == "s3cret-pw"


def test_build_secret_attaches_owner_when_given():
    s = m.build_secret("mc1", NS, "pw", owner=m.owner_reference("mc1", "u1"))
    assert s["metadata"]["ownerReferences"][0]["uid"] == "u1"


# --- service -----------------------------------------------------------------

def test_service_is_loadbalancer_with_game_and_rcon_ports():
    svc = m.build_service("mc1", NS, MC_GAME, rcon_enabled=True)
    assert svc["spec"]["type"] == "LoadBalancer"
    assert svc["spec"]["selector"]["quetzel.gg/server"] == "mc1"
    ports = {p["name"]: p for p in svc["spec"]["ports"]}
    assert ports["game"]["port"] == 25565
    assert ports["game"]["protocol"] == "TCP"
    assert "rcon" in ports
    assert ports["rcon"]["port"] == 25575
    assert ports["rcon"]["protocol"] == "TCP"


def test_service_omits_rcon_when_disabled():
    svc = m.build_service("v1", NS, UDP_GAME, rcon_enabled=False)
    names = {p["name"] for p in svc["spec"]["ports"]}
    assert names == {"game", "query"}
    assert all(p["protocol"] == "UDP" for p in svc["spec"]["ports"])


# --- statefulset -------------------------------------------------------------

def test_statefulset_core_shape():
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    assert ss["kind"] == "StatefulSet"
    assert ss["spec"]["replicas"] == 1
    assert ss["spec"]["serviceName"] == "mc1"
    c = ss["spec"]["template"]["spec"]["containers"][0]
    assert c["image"] == "itzg/minecraft-server:latest"


def test_statefulset_image_override_wins():
    spec = {**MC_SPEC, "image": "myrepo/mc:custom"}
    ss = m.build_statefulset("mc1", NS, spec, MC_GAME)
    c = ss["spec"]["template"]["spec"]["containers"][0]
    assert c["image"] == "myrepo/mc:custom"


def test_statefulset_env_merges_defaults_overrides_and_version():
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    c = ss["spec"]["template"]["spec"]["containers"][0]
    env = {e["name"]: e for e in c["env"]}
    assert env["EULA"]["value"] == "TRUE"          # catalog default
    assert env["MOTD"]["value"] == "hello"         # user override
    assert env["VERSION"]["value"] == "1.21.1"     # versionEnv mapping
    # RCON password injected from the Secret, never inlined as a literal value
    assert env["RCON_PASSWORD"]["valueFrom"]["secretKeyRef"]["name"] == "mc1-rcon"
    assert "value" not in env["RCON_PASSWORD"]
    assert env["ENABLE_RCON"]["value"] == "true"


def test_statefulset_no_rcon_env_when_game_has_no_rcon():
    ss = m.build_statefulset("v1", NS, {**MC_SPEC, "game": "valheim"}, UDP_GAME)
    c = ss["spec"]["template"]["spec"]["containers"][0]
    names = {e["name"] for e in c["env"]}
    assert "RCON_PASSWORD" not in names


def test_statefulset_pvc_uses_storage_size_and_mounts_data_path():
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    vct = ss["spec"]["volumeClaimTemplates"][0]
    assert vct["spec"]["resources"]["requests"]["storage"] == "3Gi"
    assert vct["spec"]["accessModes"] == ["ReadWriteOnce"]
    mount = ss["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
    assert mount["mountPath"] == "/data"
    assert mount["name"] == vct["metadata"]["name"]


def test_statefulset_has_readiness_probe_on_game_port():
    # P5: readiness gates the Running phase.
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    c = ss["spec"]["template"]["spec"]["containers"][0]
    assert c["readinessProbe"]["tcpSocket"]["port"] == 25565


def test_statefulset_has_graceful_prestop_and_grace_period():
    # P5: graceful save+stop before termination.
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    pod = ss["spec"]["template"]["spec"]
    c = pod["containers"][0]
    assert pod["terminationGracePeriodSeconds"] >= 30
    cmd = " ".join(c["lifecycle"]["preStop"]["exec"]["command"])
    assert "rcon-cli" in cmd and "stop" in cmd


def test_statefulset_sets_resources_requests_and_limits():
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME)
    res = ss["spec"]["template"]["spec"]["containers"][0]["resources"]
    assert res["requests"]["cpu"] == "1"
    assert res["limits"]["memory"] == "2Gi"


def test_children_attach_owner_reference():
    owner = m.owner_reference("mc1", "u1")
    ss = m.build_statefulset("mc1", NS, MC_SPEC, MC_GAME, owner=owner)
    svc = m.build_service("mc1", NS, MC_GAME, rcon_enabled=True, owner=owner)
    assert ss["metadata"]["ownerReferences"][0]["uid"] == "u1"
    assert svc["metadata"]["ownerReferences"][0]["uid"] == "u1"
