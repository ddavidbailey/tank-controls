import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tank_controls.config.errors import ConfigError


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

    return Config(profile_name=profile_name, press=press, hold=hold, mouse=mouse)
