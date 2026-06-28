"""WP-D tests: bootstrap admin, k8s.py round-trip, cluster registry, cross-cluster rollup."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth.context import AuthContext, set_token_verifier
from app.auth.jwt import JWTConfig, build_token_verifier, issue_token
from app.auth.roles import Role
from app.clusters.registry import (
    ClusterRef,
    LocalClusterRegistry,
    MockMultiClusterRegistry,
    RemoteClusterRegistry,
    make_cluster_registry,
    provider_for_cluster,
)
from app.deps import get_cluster_registry, get_customer_store, get_provider, get_user_store
from app.providers.mock import MockProvider
from app.tenancy.store import InMemoryCustomerStore
from app.users.store import InMemoryUserStore


# ---------------------------------------------------------------------------
# Bootstrap admin
# ---------------------------------------------------------------------------


class TestBootstrapAdmin:
    def test_no_op_when_password_unset(self, monkeypatch):
        from app.auth.bootstrap import bootstrap_admin

        monkeypatch.delenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
        store = InMemoryUserStore()
        result = bootstrap_admin(store)
        assert result is None
        assert store.list_users() == []

    def test_creates_admin_when_env_set(self, monkeypatch):
        from app.auth.bootstrap import bootstrap_admin

        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_USER", "sysadmin")
        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD", "s3cr3t!")
        store = InMemoryUserStore()
        uid = bootstrap_admin(store)
        assert uid is not None
        u = store.get_by_username("sysadmin")
        assert u is not None
        assert u.role == Role.platform_admin
        assert u.customer_id is None

    def test_idempotent_second_call(self, monkeypatch):
        from app.auth.bootstrap import bootstrap_admin

        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_USER", "admin")
        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD", "adminpw")
        store = InMemoryUserStore()
        uid1 = bootstrap_admin(store)
        uid2 = bootstrap_admin(store)
        assert uid1 == uid2
        assert len(store.list_users()) == 1

    def test_default_username_is_admin(self, monkeypatch):
        from app.auth.bootstrap import bootstrap_admin

        monkeypatch.delenv("QUETZEL_BOOTSTRAP_ADMIN_USER", raising=False)
        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD", "pw!")
        store = InMemoryUserStore()
        bootstrap_admin(store)
        assert store.get_by_username("admin") is not None

    def test_password_not_logged_or_returned(self, monkeypatch):
        """bootstrap_admin must not expose the plaintext password."""
        from app.auth.bootstrap import bootstrap_admin

        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_USER", "admin")
        monkeypatch.setenv("QUETZEL_BOOTSTRAP_ADMIN_PASSWORD", "supersecret!")
        store = InMemoryUserStore()
        uid = bootstrap_admin(store)
        u = store.get(uid)
        assert "supersecret!" not in u.password_hash


# ---------------------------------------------------------------------------
# k8s.py round-trip (customer + maxPlayers in _to_server and create_server)
# ---------------------------------------------------------------------------


class TestK8sProviderRoundTrip:
    """Unit-test the pure _to_server and create_server logic without a real cluster."""

    def _make_cr(self, extra_spec: dict) -> dict:
        spec = {
            "game": "minecraft",
            "version": "1.20.4",
            "storageSize": "2Gi",
            "env": {},
            "rconEnabled": False,
        }
        spec.update(extra_spec)
        return {
            "metadata": {"name": "test-srv", "creationTimestamp": None},
            "spec": spec,
            "status": {},
        }

    def test_to_server_reads_customer(self):
        from app.providers.k8s import K8sProvider

        provider = K8sProvider.__new__(K8sProvider)
        cr = self._make_cr({"customer": "acme"})
        srv = provider._to_server(cr)
        assert srv.spec.customer == "acme"

    def test_to_server_reads_max_players(self):
        from app.providers.k8s import K8sProvider

        provider = K8sProvider.__new__(K8sProvider)
        cr = self._make_cr({"maxPlayers": 20})
        srv = provider._to_server(cr)
        assert srv.spec.maxPlayers == 20

    def test_to_server_missing_customer_is_none(self):
        from app.providers.k8s import K8sProvider

        provider = K8sProvider.__new__(K8sProvider)
        cr = self._make_cr({})
        srv = provider._to_server(cr)
        assert srv.spec.customer is None

    def test_to_server_missing_max_players_is_none(self):
        from app.providers.k8s import K8sProvider

        provider = K8sProvider.__new__(K8sProvider)
        cr = self._make_cr({})
        srv = provider._to_server(cr)
        assert srv.spec.maxPlayers is None

    def test_create_server_includes_customer_in_spec(self):
        """create_server must write opts['customer'] into the CR spec dict."""
        from app import catalog
        from app.models import CreateServerRequest
        from app.providers.k8s import K8sProvider

        provider = K8sProvider.__new__(K8sProvider)
        # Intercept the actual k8s call
        captured = {}

        def fake_create(group, version, ns, plural, body):
            captured["body"] = body
            # Return a minimal CR dict so _to_server works
            return {
                "metadata": {"name": body["metadata"]["name"], "creationTimestamp": None},
                "spec": body["spec"],
                "status": {},
            }

        provider._api = MagicMock()
        provider._api.create_namespaced_custom_object.side_effect = fake_create
        provider.namespace = "quetzel"

        req = CreateServerRequest(
            name="mc-acme",
            game="minecraft",
            options={"customer": "acme", "maxPlayers": 4},
        )
        asyncio.run(provider.create_server(req))

        assert captured["body"]["spec"]["customer"] == "acme"
        assert captured["body"]["spec"]["maxPlayers"] == 4


# ---------------------------------------------------------------------------
# Tenancy round-trip with MockProvider (the seam that verify.sh exercises)
# ---------------------------------------------------------------------------


class TestMockProviderTenancyRoundTrip:
    def test_customer_user_sees_only_own_servers(self):
        """customer is stored on spec and visible_servers filters correctly."""
        from app.models import CreateServerRequest
        from app.tenancy.scope import visible_servers

        mock = MockProvider()

        async def _run():
            await mock.create_server(CreateServerRequest(
                name="acme-1", game="minecraft", options={"customer": "acme"}
            ))
            await mock.create_server(CreateServerRequest(
                name="globex-1", game="minecraft", options={"customer": "globex"}
            ))
            return await mock.list_servers()

        servers = asyncio.run(_run())
        assert len(servers) == 2

        acme_user = AuthContext("u1", "acme-u", Role.customer_user, "acme")
        acme_visible = visible_servers(acme_user, servers)
        assert len(acme_visible) == 1
        assert acme_visible[0].name == "acme-1"

        admin = AuthContext("a", "admin", Role.platform_admin, None)
        assert len(visible_servers(admin, servers)) == 2

    def test_admin_list_all_via_api(self, client):
        """Via the actual FastAPI app: admin sees both customers' servers."""
        client.post("/servers", json={"name": "s1", "game": "minecraft", "options": {"customer": "cx"}})
        client.post("/servers", json={"name": "s2", "game": "minecraft", "options": {"customer": "cy"}})
        r = client.get("/servers")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_customer_user_list_via_api_with_overridden_verifier(self):
        """Wire a real JWT verifier; customer-user gets only their server.

        set_token_verifier is called INSIDE the TestClient context so it
        overrides the lifespan's reset to None.
        """
        cfg = JWTConfig(secret="test-secret-at-least-32-chars-long!", algorithm="HS256", ttl=3600)

        mock = MockProvider()
        main.app.dependency_overrides[get_provider] = lambda: mock

        # Pre-issue tokens before entering the test client
        admin_tok = issue_token(cfg, user_id="adm", username="admin", role="platform-admin", customer_id=None)
        cx_tok = issue_token(cfg, user_id="cx-u", username="cx-user", role="customer-user", customer_id="cx")

        try:
            with TestClient(main.app) as c:
                # Wire verifier after lifespan startup so it takes effect
                set_token_verifier(build_token_verifier(cfg))

                # Create two servers as admin (with explicit customer option)
                admin_hdr = {"Authorization": f"Bearer {admin_tok}"}
                r1 = c.post("/servers", json={"name": "cx-s1", "game": "minecraft", "options": {"customer": "cx"}}, headers=admin_hdr)
                assert r1.status_code == 201, r1.text
                r2 = c.post("/servers", json={"name": "cy-s1", "game": "minecraft", "options": {"customer": "cy"}}, headers=admin_hdr)
                assert r2.status_code == 201, r2.text

                # cx-user token: should only see cx's server
                r = c.get("/servers", headers={"Authorization": f"Bearer {cx_tok}"})
                assert r.status_code == 200
                names = [s["name"] for s in r.json()]
                assert names == ["cx-s1"]
        finally:
            main.app.dependency_overrides.clear()
            set_token_verifier(None)


# ---------------------------------------------------------------------------
# ClusterRegistry implementations
# ---------------------------------------------------------------------------


class TestClusterRegistry:
    def test_local_registry_returns_one_cluster(self):
        reg = LocalClusterRegistry()
        clusters = reg.list_clusters()
        assert len(clusters) == 1
        assert clusters[0].local is True

    def test_local_registry_get_known(self):
        reg = LocalClusterRegistry()
        assert reg.get("local") is not None

    def test_local_registry_get_unknown(self):
        reg = LocalClusterRegistry()
        assert reg.get("other") is None

    def test_remote_registry_register_and_list(self):
        reg = RemoteClusterRegistry()
        ref = ClusterRef(id="c1", name="cluster-one", local=False)
        reg.register(ref)
        assert reg.get("c1") == ref
        assert len(reg.list_clusters()) == 1

    def test_remote_registry_get_stored_provider(self):
        reg = RemoteClusterRegistry()
        mock = MockProvider()
        ref = ClusterRef(id="c1", name="cluster-one", local=False)
        reg.register(ref, mock)
        assert reg.get_provider("c1") is mock

    def test_mock_multi_registry_two_clusters(self):
        reg = MockMultiClusterRegistry()
        clusters = reg.list_clusters()
        assert len(clusters) == 2
        ids = {c.id for c in clusters}
        assert "local" in ids
        assert "remote-1" in ids

    def test_mock_multi_remote_has_provider(self):
        reg = MockMultiClusterRegistry()
        prov = reg.get_provider("remote-1")
        assert prov is not None
        assert isinstance(prov, MockProvider)

    def test_make_cluster_registry_local(self, monkeypatch):
        monkeypatch.setenv("QUETZEL_CLUSTERS", "local")
        reg = make_cluster_registry()
        assert isinstance(reg, LocalClusterRegistry)

    def test_make_cluster_registry_mock_multi(self, monkeypatch):
        monkeypatch.setenv("QUETZEL_CLUSTERS", "mock-multi")
        reg = make_cluster_registry()
        assert isinstance(reg, MockMultiClusterRegistry)

    def test_make_cluster_registry_remote(self, monkeypatch):
        monkeypatch.setenv("QUETZEL_CLUSTERS", "remote")
        reg = make_cluster_registry()
        assert isinstance(reg, RemoteClusterRegistry)
        assert not isinstance(reg, MockMultiClusterRegistry)


# ---------------------------------------------------------------------------
# provider_for_cluster
# ---------------------------------------------------------------------------


class TestProviderForCluster:
    def test_local_cluster_delegates_to_process_provider(self):
        ref = ClusterRef(id="local", name="local", local=True)
        # No registry needed for local
        prov = provider_for_cluster(ref, registry=None)
        # Should be whatever get_provider() returns (MockProvider in tests)
        assert prov is not None

    def test_remote_cluster_uses_stored_provider(self):
        reg = RemoteClusterRegistry()
        mock = MockProvider()
        ref = ClusterRef(id="r1", name="remote-one", local=False)
        reg.register(ref, mock)
        prov = provider_for_cluster(ref, registry=reg)
        assert prov is mock

    def test_remote_cluster_no_provider_raises(self):
        reg = RemoteClusterRegistry()
        ref = ClusterRef(id="r2", name="unregistered", local=False)
        reg.register(ref)  # no provider
        with pytest.raises(NotImplementedError):
            provider_for_cluster(ref, registry=reg)


# ---------------------------------------------------------------------------
# Cross-cluster aggregation (rollup) via API
# ---------------------------------------------------------------------------


class TestCrossClusterRollup:
    def _client_with_multi(self):
        reg = MockMultiClusterRegistry()
        mock_local = MockProvider()
        # Seed one server per cluster
        asyncio.run(mock_local.create_server(
            __import__("app.models", fromlist=["CreateServerRequest"]).CreateServerRequest(
                name="local-srv", game="minecraft", options={"customer": "cx"}
            )
        ))
        # Register the local cluster's MockProvider into the registry too
        local_ref = reg.get("local")
        reg.register(local_ref, mock_local)

        main.app.dependency_overrides[get_provider] = lambda: mock_local
        main.app.dependency_overrides[get_cluster_registry] = lambda: reg
        return TestClient(main.app), reg

    def test_rollup_includes_remote_cluster(self):
        reg = MockMultiClusterRegistry()
        from app.models import CreateServerRequest

        mock_local = MockProvider()
        asyncio.run(mock_local.create_server(
            CreateServerRequest(name="local-s", game="minecraft", options={"customer": "cx"})
        ))
        # seed remote provider
        remote_mock = reg.get_provider("remote-1")
        assert remote_mock is not None
        asyncio.run(remote_mock.create_server(
            CreateServerRequest(name="remote-s", game="minecraft", options={"customer": "cx"})
        ))

        local_ref = reg.get("local")
        reg.register(local_ref, mock_local)

        main.app.dependency_overrides[get_provider] = lambda: mock_local
        main.app.dependency_overrides[get_cluster_registry] = lambda: reg

        try:
            with TestClient(main.app) as c:
                r = c.get("/clusters/rollup/servers")
                assert r.status_code == 200
                names = {s["name"] for s in r.json()}
                assert "local-s" in names
                assert "remote-s" in names
        finally:
            main.app.dependency_overrides.clear()

    def test_cluster_servers_endpoint_local(self):
        mock = MockProvider()
        reg = LocalClusterRegistry()

        from app.models import CreateServerRequest
        asyncio.run(mock.create_server(CreateServerRequest(name="srv1", game="minecraft")))

        main.app.dependency_overrides[get_provider] = lambda: mock
        main.app.dependency_overrides[get_cluster_registry] = lambda: reg
        try:
            with TestClient(main.app) as c:
                r = c.get("/clusters/local/servers")
                assert r.status_code == 200
                assert any(s["name"] == "srv1" for s in r.json())
        finally:
            main.app.dependency_overrides.clear()

    def test_cluster_unknown_returns_404(self):
        reg = LocalClusterRegistry()
        main.app.dependency_overrides[get_cluster_registry] = lambda: reg
        try:
            with TestClient(main.app) as c:
                r = c.get("/clusters/no-such-cluster/servers")
                assert r.status_code == 404
        finally:
            main.app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Customer cross-cluster server endpoint
# ---------------------------------------------------------------------------


class TestCustomerCrossClusterServers:
    def test_customer_servers_multi_cluster_merge(self):
        from app.models import CreateServerRequest

        reg = MockMultiClusterRegistry()
        mock_local = MockProvider()
        asyncio.run(mock_local.create_server(
            CreateServerRequest(name="local-cx", game="minecraft", options={"customer": "cx"})
        ))
        asyncio.run(mock_local.create_server(
            CreateServerRequest(name="local-cy", game="minecraft", options={"customer": "cy"})
        ))
        remote_mock = reg.get_provider("remote-1")
        asyncio.run(remote_mock.create_server(
            CreateServerRequest(name="remote-cx", game="minecraft", options={"customer": "cx"})
        ))

        local_ref = reg.get("local")
        reg.register(local_ref, mock_local)

        main.app.dependency_overrides[get_provider] = lambda: mock_local
        main.app.dependency_overrides[get_cluster_registry] = lambda: reg

        try:
            with TestClient(main.app) as c:
                r = c.get("/customers/cx/servers")
                assert r.status_code == 200
                names = {s["name"] for s in r.json()}
                assert "local-cx" in names
                assert "remote-cx" in names
                # cy's server should NOT appear
                assert "local-cy" not in names
        finally:
            main.app.dependency_overrides.clear()
