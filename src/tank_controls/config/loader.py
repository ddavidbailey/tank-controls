import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tank_controls.config.errors import ConfigError, EmptyKeybindError


@dataclass
class Config:
    profile_name: str
    press: dict[str, str] = field(default_factory=dict)
    hold: dict[str, str] = field(default_factory=dict)
    mouse: dict[str, str] = field(default_factory=dict)


def load_config(path: Path) -> Config:
    try:
        with open(path, "rb") as f:
            data: dict[str, Any] = tomllib.load(f)
    except FileNotFoundError:
        raise ConfigError(f"Config file not found: {path}")
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Invalid TOML in {path}: {e}")

    profile: dict[str, Any] = data.get("profile", {})
    profile_name: str = profile.get("name", "default")
    press: dict[str, str] = data.get("press", {})
    hold: dict[str, str] = data.get("hold", {})
    mouse: dict[str, str] = data.get("mouse", {})

    _validate_emptiness(press, "press")
    _validate_emptiness(hold, "hold")
    _validate_emptiness(mouse, "mouse")

    return Config(profile_name=profile_name, press=press, hold=hold, mouse=mouse)


def _validate_emptiness(section: dict[str, str], section_name: str) -> None:
    for action, binding in section.items():
        if not binding:
            raise EmptyKeybindError(
                f'[{section_name}] {action} = "" — key binding cannot be empty'
            )
