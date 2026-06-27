from app import catalog

REQUIRED_KEYS = {
    "id",
    "name",
    "description",
    "image",
    "protocol",
    "ports",
    "rcon",
    "versions",
    "defaultEnv",
    "accent",
    "icon",
}


def test_catalog_not_empty_and_has_two_plus_games():
    # DoD requires at least 2 games in the library.
    assert len(catalog.list_games()) >= 2


def test_every_entry_has_required_keys_and_shape():
    for g in catalog.list_games():
        assert REQUIRED_KEYS <= set(g), f"{g.get('id')} missing keys"
        assert g["versions"], f"{g['id']} must have >=1 version"
        assert g["ports"], f"{g['id']} must expose >=1 port"
        for p in g["ports"]:
            assert {"name", "port", "protocol"} <= set(p)
            assert isinstance(p["port"], int)
        assert g["protocol"] in ("tcp", "udp")
        assert g["accent"].startswith("#")


def test_ids_are_unique():
    ids = [g["id"] for g in catalog.list_games()]
    assert len(ids) == len(set(ids))


def test_get_game_known_and_unknown():
    assert catalog.get_game("minecraft")["name"] == "Minecraft"
    assert catalog.get_game("does-not-exist") is None


def test_default_version_is_first_listed():
    mc = catalog.get_game("minecraft")
    assert catalog.default_version("minecraft") == mc["versions"][0]
    assert catalog.default_version("nope") is None


def test_minecraft_accepts_eula_explicitly():
    # Security hygiene: EULA must be visible/explicit in the catalog.
    assert catalog.get_game("minecraft")["defaultEnv"].get("EULA") == "TRUE"
