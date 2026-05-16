from pathlib import Path

import pytest

from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import Config, load_config


def test_load_full_config(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text(
        '[profile]\nname = "realistic"\n\n'
        '[press]\nfire = "space"\n\n'
        '[hold]\nthrottle_up = "w"\n\n'
        '[mouse]\nturret_traverse = "relative"\n'
    )
    config = load_config(f)
    assert config.profile_name == "realistic"
    assert config.press == {"fire": "space"}
    assert config.hold == {"throttle_up": "w"}
    assert config.mouse == {"turret_traverse": "relative"}


def test_profile_name_defaults_to_default(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = "space"\n')
    assert load_config(f).profile_name == "default"


def test_all_sections_optional(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "minimal"\n')
    config = load_config(f)
    assert config.press == {}
    assert config.hold == {}
    assert config.mouse == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_invalid_toml_raises(tmp_path: Path) -> None:
    f = tmp_path / "bad.toml"
    f.write_text("not valid toml ][")
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(f)
