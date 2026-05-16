# Phase A: Config Reader + Dry-Run Logger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a TOML config reader with full validation and a dry-run logger that previews what keyboard/mouse actions would be sent to the OS.

**Architecture:** `config/errors.py` defines the exception hierarchy; `config/loader.py` reads and validates the TOML file returning a typed `Config` dataclass; `hid/dry_run.py` logs resolved actions at INFO level; `main.py` wires the CLI, loader, and logger together.

**Tech Stack:** Python 3.11+ (`tomllib` built-in), `argparse`, `logging`, `pytest`, mypy strict

---

### Task 1: Exception hierarchy

**Files:**
- Create: `tests/config/__init__.py`
- Create: `tests/hid/__init__.py`
- Create: `tests/config/test_errors.py`
- Create: `src/tank_controls/config/errors.py`

- [ ] **Step 1: Create test subdirectory packages**

Create these as empty files:
- `tests/config/__init__.py`
- `tests/hid/__init__.py`

- [ ] **Step 2: Write failing exception hierarchy tests**

Create `tests/config/test_errors.py`:

```python
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
```

- [ ] **Step 3: Run to verify tests fail**

```bash
uv run pytest tests/config/test_errors.py -v
```

Expected: `ModuleNotFoundError: No module named 'tank_controls.config.errors'`

- [ ] **Step 4: Implement errors.py**

Create `src/tank_controls/config/errors.py`:

```python
class ConfigError(Exception):
    pass


class EmptyKeybindError(ConfigError):
    pass


class InvalidKeybindError(ConfigError):
    pass


class DoubleBoundKeyError(ConfigError):
    pass
```

- [ ] **Step 5: Run to verify tests pass**

```bash
uv run pytest tests/config/test_errors.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/config/errors.py tests/config/__init__.py tests/hid/__init__.py tests/config/test_errors.py
git commit -m "feat: add config exception hierarchy"
```

---

### Task 2: Config dataclass and file loading

**Files:**
- Create: `tests/config/test_loader.py`
- Create: `src/tank_controls/config/loader.py`

- [ ] **Step 1: Write failing loader tests**

Create `tests/config/test_loader.py`:

```python
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
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/config/test_loader.py -v
```

Expected: `ModuleNotFoundError: No module named 'tank_controls.config.loader'`

- [ ] **Step 3: Implement loader.py**

Create `src/tank_controls/config/loader.py`:

```python
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
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/config/test_loader.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add Config dataclass and TOML file loading"
```

---

### Task 3: Empty keybind validation

**Files:**
- Modify: `tests/config/test_loader.py` (append)
- Modify: `src/tank_controls/config/loader.py`

- [ ] **Step 1: Append failing empty-keybind tests**

Add this import at the top of `tests/config/test_loader.py` (update the existing errors import line):

```python
from tank_controls.config.errors import ConfigError, EmptyKeybindError
```

Append these test functions at the end of `tests/config/test_loader.py`:

```python
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
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
uv run pytest tests/config/test_loader.py::test_empty_press_keybind_raises tests/config/test_loader.py::test_empty_hold_keybind_raises tests/config/test_loader.py::test_empty_mouse_keybind_raises -v
```

Expected: all 3 FAIL — `load_config` returns a Config without raising.

- [ ] **Step 3: Add emptiness validation to loader.py**

Replace `src/tank_controls/config/loader.py` with:

```python
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
```

- [ ] **Step 4: Run to verify all loader tests pass**

```bash
uv run pytest tests/config/test_loader.py -v
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add empty keybind validation"
```

---

### Task 4: Invalid keybind validation

**Files:**
- Modify: `tests/config/test_loader.py` (append)
- Modify: `src/tank_controls/config/loader.py`

- [ ] **Step 1: Append failing invalid-keybind tests**

Update the errors import line at the top of `tests/config/test_loader.py`:

```python
from tank_controls.config.errors import ConfigError, EmptyKeybindError, InvalidKeybindError
```

Append these test functions:

```python
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
```

- [ ] **Step 2: Run to verify the two validation tests fail**

```bash
uv run pytest tests/config/test_loader.py::test_invalid_press_keybind_raises tests/config/test_loader.py::test_invalid_mouse_value_raises -v
```

Expected: both FAIL — no pattern check yet.

- [ ] **Step 3: Replace loader.py with pattern validation**

Replace `src/tank_controls/config/loader.py` with:

```python
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
            raise InvalidKeybindError(
                f'[mouse] {action} = "{binding}" — expected one of: {", ".join(sorted(_MOUSE_VALID_VALUES))}'
            )
```

Note: `_validate_emptiness` from Task 3 is replaced by `_validate_key_section` and `_validate_mouse_section`, which include the empty check plus pattern/value validation.

- [ ] **Step 4: Run to verify all loader tests pass**

```bash
uv run pytest tests/config/test_loader.py -v
```

Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add invalid keybind and mouse value validation"
```

---

### Task 5: Cross-section duplicate validation

**Files:**
- Modify: `tests/config/test_loader.py` (append)
- Modify: `src/tank_controls/config/loader.py`

- [ ] **Step 1: Append failing duplicate-key tests**

Update the errors import line at the top of `tests/config/test_loader.py`:

```python
from tank_controls.config.errors import (
    ConfigError,
    DoubleBoundKeyError,
    EmptyKeybindError,
    InvalidKeybindError,
)
```

Append these test functions:

```python
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
```

- [ ] **Step 2: Run to verify the duplicate test fails**

```bash
uv run pytest tests/config/test_loader.py::test_cross_section_duplicate_raises -v
```

Expected: FAIL — `load_config` returns a Config without raising.

- [ ] **Step 3: Add cross-section duplicate check to loader.py**

Replace `src/tank_controls/config/loader.py` with:

```python
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
    _validate_no_cross_section_duplicates(press, hold, mouse)

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
            raise InvalidKeybindError(
                f'[mouse] {action} = "{binding}" — expected one of: {", ".join(sorted(_MOUSE_VALID_VALUES))}'
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
```

- [ ] **Step 4: Run to verify all loader tests pass**

```bash
uv run pytest tests/config/test_loader.py -v
```

Expected: `16 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add cross-section duplicate keybind validation"
```

---

### Task 6: Dry-run logger

**Files:**
- Create: `tests/hid/test_dry_run.py`
- Create: `src/tank_controls/hid/dry_run.py`

- [ ] **Step 1: Write failing dry-run logger tests**

Create `tests/hid/test_dry_run.py`:

```python
import logging

import pytest

from tank_controls.hid.dry_run import log_action


def test_log_press_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("fire", "press", "space")
    assert "[DRY-RUN] press: space (fire)" in caplog.text


def test_log_hold_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("throttle_up", "hold", "w")
    assert "[DRY-RUN] hold: w (throttle_up)" in caplog.text


def test_log_mouse_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("turret_traverse", "mouse_move", "relative")
    assert "[DRY-RUN] mouse_move: relative (turret_traverse)" in caplog.text
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/hid/test_dry_run.py -v
```

Expected: `ModuleNotFoundError: No module named 'tank_controls.hid.dry_run'`

- [ ] **Step 3: Implement dry_run.py**

Create `src/tank_controls/hid/dry_run.py`:

```python
import logging

logger = logging.getLogger(__name__)


def log_action(action_name: str, action_type: str, binding: str) -> None:
    logger.info("[DRY-RUN] %s: %s (%s)", action_type, binding, action_name)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
uv run pytest tests/hid/test_dry_run.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/hid/dry_run.py tests/hid/test_dry_run.py
git commit -m "feat: add dry-run action logger"
```

---

### Task 7: CLI entry point

**Files:**
- Create: `tests/test_main.py`
- Modify: `src/tank_controls/main.py`

- [ ] **Step 1: Write failing main tests**

Create `tests/test_main.py`:

```python
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from tank_controls.main import main


def test_main_logs_actions(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')
    with patch("sys.argv", ["tank-controls", "--config", str(f)]):
        with caplog.at_level(logging.INFO):
            main()
    assert "[DRY-RUN] press: space (fire)" in caplog.text


def test_main_exits_on_missing_config(tmp_path: Path) -> None:
    with patch("sys.argv", ["tank-controls", "--config", str(tmp_path / "missing.toml")]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_main_exits_on_config_error(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = ""\n')
    with patch("sys.argv", ["tank-controls", "--config", str(f)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1
```

- [ ] **Step 2: Run to verify tests fail**

```bash
uv run pytest tests/test_main.py -v
```

Expected: all 3 FAIL — current `main()` is a no-op.

- [ ] **Step 3: Implement main.py**

Replace `src/tank_controls/main.py` with:

```python
import argparse
import logging
import sys
from pathlib import Path

from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import load_config
from tank_controls.hid.dry_run import log_action


def main() -> None:
    parser = argparse.ArgumentParser(description="War Thunder multimodal controls")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to keybind config file (default: config.toml)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as e:
        logging.error(str(e))
        sys.exit(1)

    logging.info("Loaded profile: %s", config.profile_name)

    for action, key in config.press.items():
        log_action(action, "press", key)
    for action, key in config.hold.items():
        log_action(action, "hold", key)
    for action, binding in config.mouse.items():
        log_action(action, "mouse_move", binding)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run full suite and verify tooling**

```bash
uv run pytest -v
```

Expected: all tests pass (previous import smoke tests + 5 + 16 + 3 + 3 = 27 total).

```bash
uv run ruff check .
uv run mypy src/
```

Expected: both clean.

- [ ] **Step 5: Commit and push**

```bash
git add src/tank_controls/main.py tests/test_main.py
git commit -m "feat: wire CLI entry point with config loader and dry-run logger"
git push origin master
```
