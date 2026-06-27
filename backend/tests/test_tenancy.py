"""Contract tests for pure tenancy scoping."""
from app.auth.context import AuthContext
from app.auth.roles import Role
from app.tenancy.scope import CUSTOMER_LABEL, visible_servers


class _Spec:
    def __init__(self, customer):
        self.customer = customer


class _Srv:
    def __init__(self, name, customer):
        self.name = name
        self.spec = _Spec(customer)


def test_label_constant():
    assert CUSTOMER_LABEL == "quetzel.gg/customer"


def test_admin_sees_all():
    admin = AuthContext("a", "a", Role.platform_admin, None)
    servers = [_Srv("s1", "cust-a"), _Srv("s2", "cust-b"), _Srv("s3", None)]
    assert len(visible_servers(admin, servers)) == 3


def test_customer_user_sees_only_own():
    user = AuthContext("u", "u", Role.customer_user, "cust-a")
    servers = [_Srv("s1", "cust-a"), _Srv("s2", "cust-b"), _Srv("s3", None), _Srv("s4", "cust-a")]
    assert [s.name for s in visible_servers(user, servers)] == ["s1", "s4"]


def test_scope_works_on_dicts():
    user = AuthContext("u", "u", Role.customer_user, "cust-a")
    servers = [{"name": "s1", "spec": {"customer": "cust-a"}}, {"name": "s2", "spec": {"customer": "cust-b"}}]
    assert [s["name"] for s in visible_servers(user, servers)] == ["s1"]
