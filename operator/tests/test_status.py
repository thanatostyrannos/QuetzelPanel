"""TDD spec for pure status-derivation helpers used by the reconciler.

No cluster needed: given plain dicts (what the k8s API returns), derive the
GameServer status the same way the live controller will.
"""
from quetzel_operator import status as st


def test_service_address_reads_loadbalancer_ingress_ip():
    svc = {"status": {"loadBalancer": {"ingress": [{"ip": "192.168.5.15"}]}}}
    assert st.service_address(svc, 25565) == "192.168.5.15:25565"


def test_service_address_falls_back_to_hostname():
    svc = {"status": {"loadBalancer": {"ingress": [{"hostname": "lb.local"}]}}}
    assert st.service_address(svc, 2456) == "lb.local:2456"


def test_service_address_none_until_assigned():
    assert st.service_address({"status": {"loadBalancer": {}}}, 25565) is None
    assert st.service_address({}, 25565) is None


def test_phase_stopping_when_deleting():
    s = st.compute_phase(deleting=True, statefulset_exists=True, ready_replicas=1, address="x:1")
    assert s["phase"] == "Stopping"
    assert s["ready"] is False


def test_phase_pending_before_statefulset():
    s = st.compute_phase(deleting=False, statefulset_exists=False, ready_replicas=0, address=None)
    assert s["phase"] == "Pending"


def test_phase_provisioning_while_pod_not_ready_or_no_address():
    s1 = st.compute_phase(deleting=False, statefulset_exists=True, ready_replicas=0, address=None)
    assert s1["phase"] == "Provisioning"
    s2 = st.compute_phase(deleting=False, statefulset_exists=True, ready_replicas=1, address=None)
    assert s2["phase"] == "Provisioning"


def test_phase_running_when_ready_and_addressed():
    s = st.compute_phase(deleting=False, statefulset_exists=True, ready_replicas=1, address="192.168.5.15:25565")
    assert s["phase"] == "Running"
    assert s["ready"] is True
    assert s["address"] == "192.168.5.15:25565"
