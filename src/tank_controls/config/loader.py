import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tank_controls.config.errors import (
    ConfigError,
    DoubleBoundKeyError,
    EmptyKeybindError,
    InvalidKeybindError,
)

_VALID_KEY = r"(?:[a-z0-9]|space|enter|tab|escape|f(?:[1-9]|1[0-2]))"
_VALID_MODIFIER = r"(?:ctrl|alt|shift)"
_BINDING_RE = re.compile(rf"^(?:{_VALID_MODIFIER}\+)*{_VALID_KEY}$")
_MOUSE_VALID_VALUES: frozenset[str] = frozenset({"relative"})


@dataclass
class VisionConfig:
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    fps: int = 30
    quadrant_threshold: float = 0.07
    max_mouse_speed: int = 15
    mouse_accel_exponent: float = 0.5


@dataclass
class VoiceConfig:
    energy_threshold: float = 300.0
    match_threshold: float = 0.8
    action_cooldown_ms: int = 200
    model: str = "mlx-community/whisper-tiny.en-mlx"


@dataclass
class Config:
    profile_name: str
    press: dict[str, str] = field(default_factory=dict)
    hold: dict[str, str] = field(default_factory=dict)
    mouse: dict[str, str] = field(default_factory=dict)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)


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
    _validate_no_cross_section_duplicates(press, hold, mouse)

    voice_raw: dict[str, Any] = data.get("voice", {})
    voice = VoiceConfig(
        energy_threshold=float(voice_raw.get("energy_threshold", 300.0)),
        match_threshold=float(voice_raw.get("match_threshold", 0.8)),
        action_cooldown_ms=int(voice_raw.get("action_cooldown_ms", 200)),
        model=str(voice_raw.get("model", "mlx-community/whisper-tiny.en-mlx")),
    )
    vision_raw: dict[str, Any] = data.get("vision", {})
    vision = VisionConfig(
        camera_index=int(vision_raw.get("camera_index", 0)),
        frame_width=int(vision_raw.get("frame_width", 640)),
        frame_height=int(vision_raw.get("frame_height", 480)),
        fps=int(vision_raw.get("fps", 30)),
        quadrant_threshold=float(vision_raw.get("quadrant_threshold", 0.07)),
        max_mouse_speed=int(vision_raw.get("max_mouse_speed", 15)),
        mouse_accel_exponent=float(vision_raw.get("mouse_accel_exponent", 0.5)),
    )
    return Config(
        profile_name=profile_name,
        press=press,
        hold=hold,
        mouse=mouse,
        voice=voice,
        vision=vision,
    )


def _validate_key_section(section: dict[str, str], section_name: str) -> None:
    for action, binding in section.items():
        if not binding:
            raise EmptyKeybindError(f'[{section_name}] {action} = "" — key binding cannot be empty')
        if not _BINDING_RE.match(binding):
            raise InvalidKeybindError(
                f'[{section_name}] {action} = "{binding}" — not a recognised key or combo'
            )


def _validate_mouse_section(section: dict[str, str]) -> None:
    for action, binding in section.items():
        if not binding:
            raise EmptyKeybindError(f'[mouse] {action} = "" — key binding cannot be empty')
        if binding not in _MOUSE_VALID_VALUES:
            valid_values = ", ".join(sorted(_MOUSE_VALID_VALUES))
            raise InvalidKeybindError(
                f'[mouse] {action} = "{binding}" — expected one of: {valid_values}'
            )


def _validate_no_cross_section_duplicates(
    press: dict[str, str],
    hold: dict[str, str],
    mouse: dict[str, str],
) -> None:
    seen: dict[str, str] = {}
    for section_name, section in (("press", press), ("hold", hold), ("mouse", mouse)):
        for action, key in section.items():
            if key in seen:
                raise DoubleBoundKeyError(
                    f"Key '{key}' is bound in both [{seen[key]}] and [{section_name}]"
                )
            seen[key] = section_name
