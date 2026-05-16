import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tank_controls.config.errors import ConfigError, EmptyKeybindError, InvalidKeybindError

_VALID_KEY = r"(?:[a-z0-9]|space|enter|tab|escape|f(?:[1-9]|1[0-2]))"
_VALID_MODIFIER = r"(?:ctrl|alt|shift)"
_BINDING_RE = re.compile(rf"^(?:{_VALID_MODIFIER}\+)*{_VALID_KEY}$")
_MOUSE_VALID_VALUES: frozenset[str] = frozenset({"relative"})


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

    _validate_key_section(press, "press")
    _validate_key_section(hold, "hold")
    _validate_mouse_section(mouse)

    return Config(profile_name=profile_name, press=press, hold=hold, mouse=mouse)


def _validate_key_section(section: dict[str, str], section_name: str) -> None:
    for action, binding in section.items():
        if not binding:
            raise EmptyKeybindError(
                f'[{section_name}] {action} = "" — key binding cannot be empty'
            )
        if not _BINDING_RE.match(binding):
            raise InvalidKeybindError(
                f'[{section_name}] {action} = "{binding}" — not a recognised key or combo'
            )


def _validate_mouse_section(section: dict[str, str]) -> None:
    for action, binding in section.items():
        if not binding:
            raise EmptyKeybindError(
                f'[mouse] {action} = "" — key binding cannot be empty'
            )
        if binding not in _MOUSE_VALID_VALUES:
            valid_values = ", ".join(sorted(_MOUSE_VALID_VALUES))
            raise InvalidKeybindError(
                f'[mouse] {action} = "{binding}" — expected one of: {valid_values}'
            )
