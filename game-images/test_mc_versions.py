"""Unit tests for the pure version logic (WP-E). No network."""
import mc_versions as mv

MANIFEST = {
    "latest": {"release": "1.21.1", "snapshot": "24w30a"},
    "versions": [
        {"id": "24w30a", "type": "snapshot", "url": "https://x/24w30a.json"},
        {"id": "1.21.1", "type": "release", "url": "https://x/1.21.1.json"},
        {"id": "1.21", "type": "release", "url": "https://x/1.21.json"},
        {"id": "1.20.4", "type": "release", "url": "https://x/1.20.4.json"},
    ],
}

PACKAGE = {
    "downloads": {
        "server": {"url": "https://piston-data/server.jar", "sha1": "abc123", "size": 49150256},
        "client": {"url": "https://piston-data/client.jar", "sha1": "deadbeef"},
    }
}


def test_latest_release():
    assert mv.latest_release(MANIFEST) == "1.21.1"


def test_find_package_url():
    assert mv.find_package_url("1.20.4", MANIFEST) == "https://x/1.20.4.json"
    assert mv.find_package_url("9.9.9", MANIFEST) is None


def test_server_download():
    d = mv.server_download(PACKAGE)
    assert d == {"url": "https://piston-data/server.jar", "sha1": "abc123", "size": 49150256}


def test_server_download_missing():
    assert mv.server_download({"downloads": {}}) is None


def test_release_ids_excludes_snapshots_newest_first():
    assert mv.release_ids(MANIFEST) == ["1.21.1", "1.21", "1.20.4"]


def test_select_new_versions_adds_latest_only():
    # known is missing the two newest releases; count=1 adds just the newest.
    assert mv.select_new_versions(["1.20.4"], MANIFEST, count=1) == ["1.21.1"]


def test_select_new_versions_up_to_date():
    assert mv.select_new_versions(["1.21.1", "1.21", "1.20.4"], MANIFEST) == []


def test_select_new_versions_count():
    assert mv.select_new_versions(["1.20.4"], MANIFEST, count=2) == ["1.21.1", "1.21"]
