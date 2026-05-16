# Project Setup Design

**Date:** 2026-05-14
**Scope:** Initial project scaffolding — packaging, dependencies, src skeleton, dev tooling

## Decision summary

- **Package manager:** uv
- **Python:** 3.11+
- **Source layout:** `src/tank_controls/` (src layout for clean import isolation)

## Dependencies

### Runtime

| Package           | Purpose                                        |
| ----------------- | ---------------------------------------------- |
| `faster-whisper`  | Local STT (tiny/base int8)                     |
| `webrtcvad`       | Voice activity detection                       |
| `mediapipe`       | Two-hand landmarks (max_hands=2)               |
| `opencv-python`   | Camera capture and frame preprocessing         |
| `sounddevice`     | Audio capture                                  |
| `pynput`          | HID output (keyboard/mouse synthesis)          |

Note: `vosk` was the original STT choice but has no macOS arm64 wheels on PyPI. `faster-whisper` is the replacement.

### Dev (dependency-groups)

`ruff`, `mypy`, `pytest`, `pytest-asyncio`

## Directory structure

```
tank-controls/
├── src/
│   └── tank_controls/
│       ├── __init__.py
│       ├── main.py          # entry point, wires pipeline together
│       ├── audio/           # AudioCapture, VAD, STT (faster-whisper)
│       │   └── __init__.py
│       ├── vision/          # FrameCapture, MediaPipe two-hand landmarks, gesture→axes
│       │   └── __init__.py
│       ├── hid/             # pynput HID output
│       │   └── __init__.py
│       └── config/          # profile loading, keybind mapping
│           └── __init__.py
├── tests/
│   └── __init__.py
├── pyproject.toml
└── CLAUDE.md
```

Each subdirectory maps to a pipeline stage. `config/` has no upstream dependencies — it is read by both `audio/` and `hid/`.

## Tooling configuration

All config in `pyproject.toml`. No separate config files.

- **Ruff:** line length 100, target py311, rule sets `E`, `F`, `I`
- **Mypy:** strict mode, source root `src/`
- **Pytest:** `asyncio_mode = "auto"`, `testpaths = ["tests"]`

### Common commands

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src/
```
