"""Catalog loader for the operator.

Single source of truth is backend/app/catalog.py; install renders it to a JSON
ConfigMap mounted at CATALOG_PATH. This loader reads that file (falling back to a
repo-local copy for dev), so the operator and backend never disagree on a game.

Regenerate the JSON after editing the catalog:
    python -c "import json; from app import catalog; \
        open('deploy/catalog.json','w').write(json.dumps({'games':catalog.list_games()},indent=2))"
"""
from __future__ import annotations

import functools
import json
import os
from pathlib import Path

_DEFAULT_PATHS = [
    os.getenv("CATALOG_PATH", ""),
    "/etc/quetzel/catalog.json",
    str(Path(__file__).resolve().parents[2] / "deploy" / "catalog.json"),
]


@functools.lru_cache(maxsize=1)
def _load() -> dict[str, dict]:
    for p in _DEFAULT_PATHS:
        if p and Path(p).is_file():
            data = json.loads(Path(p).read_text())
            return {g["id"]: g for g in data.get("games", [])}
    raise FileNotFoundError(
        "catalog.json not found; set CATALOG_PATH or render deploy/catalog.json"
    )


def get_game(game_id: str) -> dict | None:
    return _load().get(game_id)


def default_version(game_id: str) -> str | None:
    g = get_game(game_id)
    return g["versions"][0] if g and g.get("versions") else None
