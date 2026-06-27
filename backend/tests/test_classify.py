"""Unit tests for the pure metrics classifiers in app.metrics.classify.

These tests run with no cluster (no kubernetes client needed).
"""
import pytest

from app.metrics.classify import (
    classify_pod,
    node_is_ready,
    cpu_percent,
    memory_percent,
    disk_percent,
    parse_cpu_to_nano,
    parse_memory_to_bytes,
    usage_cpu_nano_from_metrics,
    usage_memory_bytes_from_metrics,
    limit_cpu_nano_from_pod,
    limit_memory_bytes_from_pod,
    waiting_reason_from_pod,
    restart_count_from_pod,
    ready_from_pod,
    disk_percent_from_summary,
    build_cluster_health,
)


# ---------------------------------------------------------------------------
# classify_pod
# ---------------------------------------------------------------------------

class TestClassifyPod:
    def test_running_ready_ok(self):
        assert classify_pod("Running", ready=True, restart_count=0) == "ok"

    def test_running_not_ready_transient_ok(self):
        # not ready but no waiting reason — still warming up
        assert classify_pod("Running", ready=False, restart_count=0) == "ok"

    def test_running_with_crashloop_reason(self):
        assert classify_pod("Running", ready=False, restart_count=3, waiting_reason="CrashLoopBackOff") == "crashloop"

    def test_running_high_restarts_crashloop(self):
        assert classify_pod("Running", ready=True, restart_count=5) == "crashloop"
        assert classify_pod("Running", ready=True, restart_count=10) == "crashloop"

    def test_running_below_threshold_ok(self):
        assert classify_pod("Running", ready=True, restart_count=4) == "ok"

    def test_running_terminal_waiting_error(self):
        assert classify_pod("Running", ready=False, restart_count=1, waiting_reason="ImagePullBackOff") == "error"
        assert classify_pod("Running", ready=False, restart_count=0, waiting_reason="ErrImagePull") == "error"

    def test_failed_phase_error(self):
        assert classify_pod("Failed", ready=False, restart_count=0) == "error"

    def test_unknown_phase_error(self):
        assert classify_pod("Unknown", ready=False, restart_count=0) == "error"

    def test_succeeded_ok(self):
        assert classify_pod("Succeeded", ready=False, restart_count=0) == "ok"

    def test_pending_no_reason_ok(self):
        assert classify_pod("Pending", ready=False, restart_count=0) == "ok"

    def test_pending_image_pull_error(self):
        assert classify_pod("Pending", ready=False, restart_count=0, waiting_reason="ErrImagePull") == "error"

    def test_crashloop_reason_overrides_ready(self):
        assert classify_pod("Running", ready=True, restart_count=0, waiting_reason="CrashLoopBackOff") == "crashloop"


# ---------------------------------------------------------------------------
# node_is_ready
# ---------------------------------------------------------------------------

class TestNodeIsReady:
    def _node(self, status_str: str):
        return {"status": {"conditions": [{"type": "Ready", "status": status_str}]}}

    def test_ready_true(self):
        assert node_is_ready(self._node("True")) is True

    def test_ready_false(self):
        assert node_is_ready(self._node("False")) is False

    def test_no_conditions(self):
        assert node_is_ready({"status": {}}) is False

    def test_no_ready_condition(self):
        node = {"status": {"conditions": [{"type": "DiskPressure", "status": "False"}]}}
        assert node_is_ready(node) is False

    def test_empty_node(self):
        assert node_is_ready({}) is False


# ---------------------------------------------------------------------------
# percent helpers
# ---------------------------------------------------------------------------

class TestPercentHelpers:
    def test_cpu_percent_basic(self):
        assert cpu_percent(500_000_000, 1_000_000_000) == 50.0

    def test_cpu_percent_capped_at_100(self):
        assert cpu_percent(2_000_000_000, 1_000_000_000) == 100.0

    def test_cpu_percent_zero_limit(self):
        assert cpu_percent(500_000_000, 0) is None

    def test_cpu_percent_none_usage(self):
        assert cpu_percent(None, 1_000_000_000) is None

    def test_memory_percent_basic(self):
        assert memory_percent(256 * 1024 * 1024, 512 * 1024 * 1024) == 50.0

    def test_memory_percent_zero_limit(self):
        assert memory_percent(100, 0) is None

    def test_disk_percent_basic(self):
        assert disk_percent(500 * 1024 * 1024, 1024 * 1024 * 1024) == pytest.approx(48.8, abs=0.2)

    def test_disk_percent_full(self):
        assert disk_percent(1024, 1024) == 100.0

    def test_disk_percent_none_capacity(self):
        assert disk_percent(100, None) is None


# ---------------------------------------------------------------------------
# Kubernetes quantity parsers
# ---------------------------------------------------------------------------

class TestQuantityParsers:
    def test_cpu_milli(self):
        assert parse_cpu_to_nano("500m") == 500_000_000

    def test_cpu_whole(self):
        assert parse_cpu_to_nano("2") == 2_000_000_000

    def test_cpu_fractional(self):
        assert parse_cpu_to_nano("0.5") == 500_000_000

    def test_memory_mi(self):
        assert parse_memory_to_bytes("512Mi") == 512 * 1024 * 1024

    def test_memory_gi(self):
        assert parse_memory_to_bytes("2Gi") == 2 * 1024 ** 3

    def test_memory_ki(self):
        assert parse_memory_to_bytes("64Ki") == 64 * 1024

    def test_memory_plain(self):
        assert parse_memory_to_bytes("1048576") == 1_048_576

    def test_memory_si_m(self):
        assert parse_memory_to_bytes("100M") == 100_000_000

    def test_memory_si_g(self):
        assert parse_memory_to_bytes("1G") == 1_000_000_000


# ---------------------------------------------------------------------------
# metrics-server dict helpers
# ---------------------------------------------------------------------------

_SAMPLE_POD_METRICS = {
    "containers": [
        {"name": "minecraft", "usage": {"cpu": "250m", "memory": "512Mi"}},
        {"name": "rcon", "usage": {"cpu": "10m", "memory": "32Mi"}},
    ]
}

_SAMPLE_POD = {
    "spec": {
        "containers": [
            {
                "name": "minecraft",
                "resources": {"limits": {"cpu": "2", "memory": "2Gi"}},
            },
            {
                "name": "rcon",
                "resources": {"limits": {"cpu": "100m", "memory": "64Mi"}},
            },
        ]
    }
}


class TestMetricsExtraction:
    def test_usage_cpu_nano(self):
        nano = usage_cpu_nano_from_metrics(_SAMPLE_POD_METRICS)
        # 250m + 10m = 260m = 260_000_000 nano
        assert nano == 260_000_000

    def test_usage_memory_bytes(self):
        b = usage_memory_bytes_from_metrics(_SAMPLE_POD_METRICS)
        # 512Mi + 32Mi = 544Mi
        assert b == 544 * 1024 * 1024

    def test_usage_empty_containers(self):
        assert usage_cpu_nano_from_metrics({}) is None
        assert usage_memory_bytes_from_metrics({"containers": []}) is None

    def test_limit_cpu_nano(self):
        nano = limit_cpu_nano_from_pod(_SAMPLE_POD)
        # 2 cores + 100m = 2100m = 2_100_000_000 nano
        assert nano == 2_100_000_000

    def test_limit_memory_bytes(self):
        b = limit_memory_bytes_from_pod(_SAMPLE_POD)
        # 2Gi + 64Mi
        assert b == (2 * 1024 ** 3) + (64 * 1024 * 1024)

    def test_limit_no_limits(self):
        pod = {"spec": {"containers": [{"name": "c", "resources": {}}]}}
        assert limit_cpu_nano_from_pod(pod) is None
        assert limit_memory_bytes_from_pod(pod) is None


# ---------------------------------------------------------------------------
# Pod status helpers
# ---------------------------------------------------------------------------

def _make_pod(phase="Running", ready=True, restarts=0, waiting_reason=None):
    conditions = [{"type": "Ready", "status": "True" if ready else "False"}]
    state = {}
    if waiting_reason:
        state = {"waiting": {"reason": waiting_reason}}
    else:
        if phase == "Running":
            state = {"running": {}}
    return {
        "status": {
            "phase": phase,
            "conditions": conditions,
            "containerStatuses": [
                {"restartCount": restarts, "state": state}
            ],
        }
    }


class TestPodHelpers:
    def test_waiting_reason(self):
        pod = _make_pod(phase="Running", ready=False, waiting_reason="CrashLoopBackOff")
        assert waiting_reason_from_pod(pod) == "CrashLoopBackOff"

    def test_no_waiting_reason(self):
        pod = _make_pod(phase="Running", ready=True)
        assert waiting_reason_from_pod(pod) is None

    def test_restart_count(self):
        pod = _make_pod(restarts=7)
        assert restart_count_from_pod(pod) == 7

    def test_ready_true(self):
        pod = _make_pod(ready=True)
        assert ready_from_pod(pod) is True

    def test_ready_false(self):
        pod = _make_pod(ready=False)
        assert ready_from_pod(pod) is False

    def test_snake_case_container_statuses(self):
        # .to_dict() may return snake_case
        pod = {
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "False"}],
                "container_statuses": [
                    {"restart_count": 3, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}
                ],
            }
        }
        assert waiting_reason_from_pod(pod) == "CrashLoopBackOff"
        assert restart_count_from_pod(pod) == 3


# ---------------------------------------------------------------------------
# disk_percent_from_summary
# ---------------------------------------------------------------------------

_SAMPLE_SUMMARY = {
    "pods": [
        {
            "podRef": {"name": "mc-demo-0", "namespace": "quetzel"},
            "volume": [
                {
                    "name": "data",
                    "pvcRef": {"name": "data-mc-demo-0"},
                    "usedBytes": 1073741824,    # 1 GiB
                    "capacityBytes": 2147483648,  # 2 GiB
                }
            ],
        }
    ]
}


class TestDiskSummary:
    def test_found(self):
        pct = disk_percent_from_summary(_SAMPLE_SUMMARY, "data-mc-demo-0")
        assert pct == 50.0

    def test_not_found(self):
        assert disk_percent_from_summary(_SAMPLE_SUMMARY, "data-other-0") is None

    def test_empty_summary(self):
        assert disk_percent_from_summary({}, "data-mc-demo-0") is None

    def test_zero_capacity(self):
        summary = {
            "pods": [
                {
                    "podRef": {"name": "x-0"},
                    "volume": [
                        {"name": "data", "pvcRef": {"name": "data-x-0"}, "usedBytes": 100, "capacityBytes": 0}
                    ],
                }
            ]
        }
        assert disk_percent_from_summary(summary, "data-x-0") is None


# ---------------------------------------------------------------------------
# build_cluster_health
# ---------------------------------------------------------------------------

def _make_node(name="node1", ready=True):
    return {
        "metadata": {"name": name},
        "status": {
            "conditions": [{"type": "Ready", "status": "True" if ready else "False"}]
        },
    }


def _make_gs(name, phase="Running", ready=True):
    return {
        "metadata": {"name": name},
        "status": {"phase": phase, "ready": ready},
    }


class TestBuildClusterHealth:
    def test_empty(self):
        h = build_cluster_health([], [], [])
        assert h["nodesTotal"] == 0
        assert h["nodesReady"] == 0
        assert h["podsRunning"] == 0
        assert h["podsError"] == 0
        assert h["problems"] == []

    def test_one_node_ready(self):
        h = build_cluster_health([_make_node("n1", ready=True)], [], [])
        assert h["nodesTotal"] == 1
        assert h["nodesReady"] == 1
        assert "node" not in " ".join(h["problems"])

    def test_node_not_ready_produces_problem(self):
        h = build_cluster_health([_make_node("n1", ready=False)], [], [])
        assert h["nodesReady"] == 0
        assert any("NotReady" in p for p in h["problems"])

    def test_running_pod_counted(self):
        pod = _make_pod(phase="Running", ready=True, restarts=0)
        pod["metadata"] = {"name": "mc-0"}
        h = build_cluster_health([], [pod], [])
        assert h["podsRunning"] == 1
        assert h["podsError"] == 0

    def test_crashloop_pod(self):
        pod = _make_pod(phase="Running", ready=False, restarts=10, waiting_reason="CrashLoopBackOff")
        pod["metadata"] = {"name": "mc-0"}
        h = build_cluster_health([], [pod], [])
        assert h["podsError"] == 1
        assert any("CrashLoop" in p for p in h["problems"])

    def test_error_pod(self):
        pod = _make_pod(phase="Failed", ready=False, restarts=0)
        pod["metadata"] = {"name": "mc-0"}
        h = build_cluster_health([], [pod], [])
        assert h["podsError"] == 1

    def test_server_desired_vs_ready(self):
        servers = [
            _make_gs("mc1", phase="Running", ready=True),
            _make_gs("mc2", phase="Provisioning", ready=False),
        ]
        h = build_cluster_health([], [], servers)
        assert h["serversDesired"] == 2
        assert h["serversReady"] == 1

    def test_cluster_name_propagated(self):
        h = build_cluster_health([], [], [], cluster_name="prod")
        assert h["cluster"] == "prod"

    def test_combined(self):
        nodes = [_make_node("n1", ready=True), _make_node("n2", ready=False)]
        pod_ok = _make_pod(phase="Running", ready=True)
        pod_ok["metadata"] = {"name": "ok-0"}
        pod_bad = _make_pod(phase="Running", ready=False, waiting_reason="CrashLoopBackOff")
        pod_bad["metadata"] = {"name": "bad-0"}
        servers = [_make_gs("srv1", "Running", True)]
        h = build_cluster_health(nodes, [pod_ok, pod_bad], servers)
        assert h["nodesReady"] == 1
        assert h["nodesTotal"] == 2
        assert h["podsRunning"] == 1
        assert h["podsError"] == 1
        assert h["serversDesired"] == 1
        assert h["serversReady"] == 1
        assert len(h["problems"]) >= 2  # NotReady node + crashloop pod
