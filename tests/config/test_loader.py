from pathlib import Path

import pytest

from tank_controls.config.errors import (
    ConfigError,
    DoubleBoundKeyError,
    EmptyKeybindError,
    InvalidKeybindError,
)
from tank_controls.config.loader import load_config


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


def test_empty_press_keybind_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = ""\n')
    with pytest.raises(EmptyKeybindError, match="fire"):
        load_config(f)


def test_empty_hold_keybind_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[hold]\nthrottle_up = ""\n')
    with pytest.raises(EmptyKeybindError, match="throttle_up"):
        load_config(f)


def test_empty_mouse_keybind_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[mouse]\nturret_traverse = ""\n')
    with pytest.raises(EmptyKeybindError, match="turret_traverse"):
        load_config(f)


def test_invalid_press_keybind_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = "ctrl+q9z"\n')
    with pytest.raises(InvalidKeybindError, match="fire"):
        load_config(f)


def test_valid_modifier_combo_accepted(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nextinguisher = "ctrl+6"\n')
    assert load_config(f).press == {"extinguisher": "ctrl+6"}


def test_valid_named_key_accepted(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = "space"\n')
    assert load_config(f).press == {"fire": "space"}


def test_valid_f_key_accepted(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nrange_finder = "f2"\n')
    assert load_config(f).press == {"range_finder": "f2"}


def test_invalid_mouse_value_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[mouse]\nturret_traverse = "absolute"\n')
    with pytest.raises(InvalidKeybindError, match="turret_traverse"):
        load_config(f)


def test_valid_mouse_relative_accepted(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[mouse]\nturret_traverse = "relative"\n')
    assert load_config(f).mouse == {"turret_traverse": "relative"}


def test_cross_section_duplicate_raises(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = "space"\n\n[hold]\nthrottle_up = "space"\n')
    with pytest.raises(DoubleBoundKeyError, match="space"):
        load_config(f)


def test_same_key_in_same_section_is_toml_error(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = "space"\nfire = "enter"\n')
    with pytest.raises(ConfigError):
        load_config(f)


def test_voice_config_defaults_when_section_absent(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text('[profile]\nname = "test"\n')
    config = load_config(cfg)
    assert config.voice.energy_threshold == 300.0
    assert config.voice.match_threshold == 0.8
    assert config.voice.action_cooldown_ms == 200
    assert config.voice.model == "mlx-community/whisper-tiny.en-mlx"


def test_voice_config_model_parsed(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text('[profile]\nname = "test"\n[voice]\nmodel = "base.en"\n')
    config = load_config(cfg)
    assert config.voice.model == "base.en"


def test_voice_config_values_parsed(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[profile]\nname = "test"\n'
        "[voice]\nenergy_threshold = 500.0\nmatch_threshold = 0.9\naction_cooldown_ms = 150\n"
    )
    config = load_config(cfg)
    assert config.voice.energy_threshold == 500.0
    assert config.voice.match_threshold == 0.9
    assert config.voice.action_cooldown_ms == 150
