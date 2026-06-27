"""Contract tests for UserStore + password hashing."""
import pytest

from app.auth.roles import Role
from app.users.store import InMemoryUserStore, hash_password, verify_password


def test_hash_roundtrip_and_salted():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    # random salt -> different encodings for the same password
    assert h != hash_password("s3cret")


def test_inmemory_store_lifecycle():
    s = InMemoryUserStore()
    u = s.create_user("alice", "pw", Role.customer_user, "cust-a")
    assert s.get(u.id).username == "alice"
    assert s.get_by_username("alice").customer_id == "cust-a"
    assert s.authenticate("alice", "pw").id == u.id
    assert s.authenticate("alice", "bad") is None
    assert s.authenticate("ghost", "pw") is None
    with pytest.raises(ValueError):
        s.create_user("alice", "x", Role.customer_user, "cust-a")


def test_password_hash_never_plaintext():
    u = InMemoryUserStore().create_user("bob", "hunter2", Role.customer_admin, "c")
    assert "hunter2" not in u.password_hash
