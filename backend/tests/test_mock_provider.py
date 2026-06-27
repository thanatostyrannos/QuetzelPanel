import pytest

from app.models import CreateServerRequest
from app.providers.mock import MockProvider
from tests.conftest import FakeClock, run


def _req(name="mc1", game="minecraft", **opts):
    return CreateServerRequest(name=name, game=game, options=opts)


def test_create_starts_pending_and_lists():
    p = MockProvider()
    srv = run(p.create_server(_req()))
    assert srv.name == "mc1"
    assert srv.status.phase == "Pending"
    assert srv.status.address is None
    assert [s.name for s in run(p.list_servers())] == ["mc1"]


def test_lifecycle_transitions_with_clock():
    clock = FakeClock()
    p = MockProvider(clock=clock, pending_until=2.0, provisioning_until=7.0)
    run(p.create_server(_req()))

    assert run(p.get_server("mc1")).status.phase == "Pending"
    clock.advance(3)
    assert run(p.get_server("mc1")).status.phase == "Provisioning"
    clock.advance(5)  # t=8 > 7
    s = run(p.get_server("mc1"))
    assert s.status.phase == "Running"
    assert s.status.ready is True
    assert s.status.address == "192.168.127.2:25565"
    assert s.status.podName == "mc1-0"


def test_create_applies_catalog_defaults_and_overrides():
    p = MockProvider()
    srv = run(p.create_server(_req(version="1.20.4", env={"MOTD": "hi"})))
    assert srv.spec.version == "1.20.4"
    # catalog default env merged with override
    assert srv.spec.env["EULA"] == "TRUE"
    assert srv.spec.env["MOTD"] == "hi"
    assert srv.spec.image == "itzg/minecraft-server:latest"


def test_default_version_when_omitted():
    p = MockProvider()
    srv = run(p.create_server(_req()))
    assert srv.spec.version == "1.21.1"  # first in catalog


def test_duplicate_name_rejected():
    p = MockProvider()
    run(p.create_server(_req()))
    with pytest.raises(ValueError, match="already exists"):
        run(p.create_server(_req()))


def test_unknown_game_rejected():
    p = MockProvider()
    with pytest.raises(ValueError, match="unknown game"):
        run(p.create_server(_req(game="halo")))


def test_delete_removes_and_returns_bool():
    p = MockProvider()
    run(p.create_server(_req()))
    assert run(p.delete_server("mc1")) is True
    assert run(p.get_server("mc1")) is None
    assert run(p.delete_server("mc1")) is False  # already gone


def test_rcon_password_generated_but_never_serialized():
    p = MockProvider()
    srv = run(p.create_server(_req()))
    rec = p._records["mc1"]
    assert rec.rcon_password and len(rec.rcon_password) >= 16
    # the password must not leak through the API model
    assert "rcon_password" not in srv.model_dump()
    assert rec.rcon_password not in str(srv.model_dump())
