import pytest
from pydantic import ValidationError

from app.models import CreateServerRequest, GameServerSpec


def test_spec_defaults():
    s = GameServerSpec(game="minecraft")
    assert s.resources.cpu == "1"
    assert s.resources.mem == "2Gi"
    assert s.storageSize == "2Gi"
    assert s.rconEnabled is True
    assert s.env == {}


@pytest.mark.parametrize(
    "name,expected",
    [
        ("mc-survival", "mc-survival"),
        ("  MC-Survival  ", "mc-survival"),  # trimmed + lowercased
        ("a", "a"),
        ("game123", "game123"),
    ],
)
def test_valid_names_are_normalized(name, expected):
    req = CreateServerRequest(name=name, game="minecraft")
    assert req.name == expected


@pytest.mark.parametrize(
    "name",
    [
        "",  # empty
        "-leading",  # leading dash
        "trailing-",  # trailing dash
        "has space",  # space
        "under_score",  # underscore
        "a" * 33,  # too long (>32)
        "weird$char",  # invalid char
    ],
)
def test_invalid_names_rejected(name):
    with pytest.raises(ValidationError):
        CreateServerRequest(name=name, game="minecraft")


def test_options_default_empty_dict():
    req = CreateServerRequest(name="x", game="valheim")
    assert req.options == {}
