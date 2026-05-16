# Phase A: Config Reader + Dry-Run Logger Design

**Date:** 2026-05-15
**Scope:** Config file format, config reader with validation, dry-run logger, CLI entry point

## Goal

Read a user-defined TOML keybind config and log what the program *would* send to the OS — without sending any real input. Proves the config UX before any HID output is wired up.

---

## Config file format

TOML file with three optional sections grouped by action type. Loaded via `--config <path>` CLI argument (defaults to `config.toml` in the current directory).

```toml
[profile]
name = "realistic"

[press]
fire = "space"
extinguisher = "ctrl+6"
scout = "t"
range_finder = "ctrl+r"

[hold]
throttle_up = "w"
throttle_down = "s"
turn_left = "a"
turn_right = "d"

[mouse]
turret_traverse = "relative"
```

- `[press]` — single key or combo, triggered once per activation
- `[hold]` — key held for the duration of the action
- `[mouse]` — mouse movement actions; `"relative"` means positional nudges
- All three sections are optional

---

## Exceptions

All exceptions inherit from `ConfigError`. Defined in `src/tank_controls/config/errors.py`.

```
ConfigError
├── EmptyKeybindError     — binding value is an empty string
├── InvalidKeybindError   — binding value is not a recognised key or combo
└── DoubleBoundKeyError   — same key assigned in two different sections (cross-section only)
```

Within-section duplicates are caught automatically by the TOML parser before validation runs. Within-section duplicate detection (e.g. two actions in `[press]` sharing a key) is out of scope for Phase A.

---

## Config reader

**File:** `src/tank_controls/config/loader.py`

- Reads the TOML file using Python's built-in `tomllib`
- Validates all bindings and raises the appropriate `ConfigError` subclass on failure
- Returns a typed `Config` dataclass:

```python
@dataclass
class Config:
    profile_name: str
    press: dict[str, str]   # action_name -> key
    hold: dict[str, str]    # action_name -> key
    mouse: dict[str, str]   # action_name -> "relative"
```

**Validation rules:**
1. Each binding value must be a non-empty string → `EmptyKeybindError`
2. Each binding value must match the pattern `[modifier+]*key` where modifier is one of `ctrl`, `alt`, `shift` and key is a single character (`a`–`z`, `0`–`9`) or a named key (`space`, `enter`, `tab`, `escape`, `f1`–`f12`) → `InvalidKeybindError`
3. No key value may appear in more than one section → `DoubleBoundKeyError`

---

## Dry-run logger

**File:** `src/tank_controls/hid/dry_run.py`

Receives a resolved action and logs it at `INFO` level using `logging.getLogger(__name__)`. Does not configure the logger itself.

Output format:
```
[DRY-RUN] press: space (fire)
[DRY-RUN] hold: w (throttle_up)
[DRY-RUN] mouse_move: relative (turret_traverse)
```

---

## Entry point

**File:** `src/tank_controls/main.py`

1. Parse `--config <path>` argument via `argparse` (default: `config.toml`)
2. Configure `logging` (level: `INFO`, format: `%(levelname)s %(message)s`)
3. Load config via `loader.py` — on `ConfigError`, log the error and exit with code 1
4. For each action across all three sections, call the dry-run logger

---

## Files created or modified

| File | Action |
|------|--------|
| `src/tank_controls/config/errors.py` | Create — `ConfigError` and subclasses |
| `src/tank_controls/config/loader.py` | Create — `Config` dataclass + `load_config()` |
| `src/tank_controls/hid/dry_run.py` | Create — `log_action()` dry-run logger |
| `src/tank_controls/main.py` | Modify — CLI wiring |
| `tests/config/test_errors.py` | Create — exception hierarchy tests |
| `tests/config/test_loader.py` | Create — config loading and validation tests |
| `tests/hid/test_dry_run.py` | Create — dry-run logger tests |
