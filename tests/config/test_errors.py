import pytest
from tank_controls.config.errors import (
    ConfigError,
    DoubleBoundKeyError,
    EmptyKeybindError,
    InvalidKeybindError,
)


def test_config_error_is_exception() -> None:
    assert issubclass(ConfigError, Exception)


def test_empty_keybind_error_is_config_error() -> None:
    assert issubclass(EmptyKeybindError, ConfigError)


def test_invalid_keybind_error_is_config_error() -> None:
    assert issubclass(InvalidKeybindError, ConfigError)


def test_double_bound_key_error_is_config_error() -> None:
    assert issubclass(DoubleBoundKeyError, ConfigError)


def test_subclasses_catchable_as_config_error() -> None:
    with pytest.raises(ConfigError):
        raise EmptyKeybindError("test")
    with pytest.raises(ConfigError):
        raise InvalidKeybindError("test")
    with pytest.raises(ConfigError):
        raise DoubleBoundKeyError("test")
