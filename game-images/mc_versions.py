#!/usr/bin/env python3
"""Minecraft version resolver + upstream watcher (WP-E).

Pure functions (no I/O) do the version math so they're unit-tested offline; thin
urllib wrappers fetch Mojang's manifests. Used by two GitHub workflows:

  game-images.yml        -> `resolve <version>`  prints "<url> <sha1>" build-args
  game-version-watch.yml -> `watch <manifest>`   adds new upstream releases to the
                            game-versions.json manifest and reports what changed

No third-party deps (stdlib only), so it runs anywhere with Python 3.
"""
from __future__ import annotations

import json
import sys
import urllib.request

MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


# --------------------------------------------------------------------------- pure
def latest_release(manifest: dict) -> str | None:
    """The newest stable (non-snapshot) release id."""
    return (manifest.get("latest") or {}).get("release")


def find_package_url(version: str, manifest: dict) -> str | None:
    """URL of a version's package descriptor, or None if the version is unknown."""
    for v in manifest.get("versions", []):
        if v.get("id") == version:
            return v.get("url")
    return None


def server_download(package: dict) -> dict | None:
    """Extract {url, sha1, size} for the server jar from a version package, or None
    (very old versions have no server download)."""
    dl = (package.get("downloads") or {}).get("server")
    if not dl or not dl.get("url"):
        return None
    return {"url": dl["url"], "sha1": dl.get("sha1", ""), "size": dl.get("size", 0)}


def release_ids(manifest: dict) -> list[str]:
    """All stable release ids, newest first (manifest order)."""
    return [v["id"] for v in manifest.get("versions", []) if v.get("type") == "release"]


def select_new_versions(known: list[str], manifest: dict, count: int = 1) -> list[str]:
    """The newest `count` stable releases not already in `known` (newest first).

    This is the watcher's policy: track the latest release(s) and leave older
    pinned versions alone, so a new Minecraft release auto-adds exactly one tag.
    """
    out: list[str] = []
    for vid in release_ids(manifest):
        if vid in known:
            continue
        out.append(vid)
        if len(out) >= count:
            break
    return out


# ---------------------------------------------------------------------------- I/O
def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 (trusted Mojang URL)
        return json.loads(r.read().decode("utf-8"))


def resolve(version: str) -> dict | None:
    """Resolve {url, sha1, size} for a Minecraft version's server jar (with I/O)."""
    manifest = fetch_json(MANIFEST_URL)
    pkg_url = find_package_url(version, manifest)
    if not pkg_url:
        return None
    return server_download(fetch_json(pkg_url))


# ---------------------------------------------------------------------------- CLI
def _cmd_resolve(version: str) -> int:
    d = resolve(version)
    if not d:
        print(f"no server jar for version {version!r}", file=sys.stderr)
        return 1
    # stdout: url sha1  (consumed as build-args by game-images.yml)
    print(f"{d['url']} {d['sha1']}")
    return 0


def _cmd_watch(manifest_path: str) -> int:
    with open(manifest_path) as f:
        gv = json.load(f)
    mc = gv.get("minecraft", {})
    known = list(mc.get("versions", []))
    manifest = fetch_json(MANIFEST_URL)
    new = select_new_versions(known, manifest, count=1)
    if not new:
        print("up-to-date")  # no change
        return 0
    mc["versions"] = known + new
    gv["minecraft"] = mc
    with open(manifest_path, "w") as f:
        json.dump(gv, f, indent=2)
        f.write("\n")
    # stdout consumed by the workflow to title the PR
    print("ADDED " + " ".join(new))
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "resolve":
        return _cmd_resolve(argv[2])
    if len(argv) >= 3 and argv[1] == "watch":
        return _cmd_watch(argv[2])
    print("usage: mc_versions.py [resolve <version> | watch <game-versions.json>]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
