# Project Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a uv-managed Python 3.11+ project with src layout, runtime dependencies, dev tooling, and an empty pipeline skeleton ready for Phase A development.

**Architecture:** Single-package src layout (`src/tank_controls/`) with four subpackages mirroring the pipeline stages (audio, vision, hid, config). All tool configuration lives in `pyproject.toml`. No application logic yet — only package structure and a no-op entry point.

**Tech Stack:** Python 3.11+, uv, hatchling (build backend), vosk, webrtcvad, mediapipe, opencv-python, sounddevice, pynput, ruff, mypy (strict), pytest + pytest-asyncio

---

### Prerequisites

Before starting, ensure the following are available on macOS:

```bash
# uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Xcode CLI tools (required to build webrtcvad from source)
xcode-select --install
```

---

### Task 1: Create pyproject.toml

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "tank-controls"
version = "0.1.0"
description = "Multimodal War Thunder controls via voice and hand gestures"
requires-python = ">=3.11"
dependencies = [
    "vosk",
    "webrtcvad",
    "mediapipe",
    "opencv-python",
    "sounddevice",
    "pynput",
]

[dependency-groups]
dev = [
    "mypy>=1.0",
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.4",
]

[project.scripts]
tank-controls = "tank_controls.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tank_controls"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I"]

[tool.mypy]
strict = true
mypy_path = "src"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Install dependencies**

```bash
uv sync --all-groups
```

Expected: uv resolves and installs all packages, creates `uv.lock`. No errors.

If `webrtcvad` fails to build (missing compiler), install the pre-built alternative:

```bash
# Replace "webrtcvad" with "webrtcvad-wheels" in pyproject.toml dependencies, then re-run:
uv sync --all-groups
```

- [ ] **Step 3: Verify uv environment**

```bash
uv run python --version
```

Expected: `Python 3.11.x` or higher.

---

### Task 2: Write import smoke tests (tests first)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_imports.py`

- [ ] **Step 1: Create tests package**

Create `tests/__init__.py` as an empty file.

- [ ] **Step 2: Write failing smoke tests**

Create `tests/test_imports.py`:

```python
import tank_controls
import tank_controls.audio
import tank_controls.config
import tank_controls.hid
import tank_controls.vision


def test_package_importable() -> None:
    assert tank_controls.__name__ == "tank_controls"


def test_submodules_importable() -> None:
    assert tank_controls.audio.__name__ == "tank_controls.audio"
    assert tank_controls.vision.__name__ == "tank_controls.vision"
    assert tank_controls.hid.__name__ == "tank_controls.hid"
    assert tank_controls.config.__name__ == "tank_controls.config"
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
uv run pytest tests/test_imports.py -v
```

Expected: `ModuleNotFoundError: No module named 'tank_controls'`

---

### Task 3: Create package skeleton

**Files:**
- Create: `src/tank_controls/__init__.py`
- Create: `src/tank_controls/main.py`
- Create: `src/tank_controls/audio/__init__.py`
- Create: `src/tank_controls/vision/__init__.py`
- Create: `src/tank_controls/hid/__init__.py`
- Create: `src/tank_controls/config/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p src/tank_controls/audio
mkdir -p src/tank_controls/vision
mkdir -p src/tank_controls/hid
mkdir -p src/tank_controls/config
```

- [ ] **Step 2: Create empty package markers**

Create the following as empty files:
- `src/tank_controls/__init__.py`
- `src/tank_controls/audio/__init__.py`
- `src/tank_controls/vision/__init__.py`
- `src/tank_controls/hid/__init__.py`
- `src/tank_controls/config/__init__.py`

- [ ] **Step 3: Create main.py entry point**

Create `src/tank_controls/main.py`:

```python
def main() -> None:
    pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Install the local package**

```bash
uv sync --all-groups
```

Expected: uv installs `tank-controls` from `src/` in editable mode. No errors.

- [ ] **Step 5: Run smoke tests — expect pass**

```bash
uv run pytest tests/test_imports.py -v
```

Expected:
```
tests/test_imports.py::test_package_importable PASSED
tests/test_imports.py::test_submodules_importable PASSED
2 passed
```

---

### Task 4: Verify tooling

**Files:** None (no changes, verification only)

- [ ] **Step 1: Run ruff check**

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 2: Run ruff format check**

```bash
uv run ruff format --check .
```

Expected: `All files are already formatted.`

- [ ] **Step 3: Run mypy**

```bash
uv run mypy src/
```

Expected: `Success: no issues found in 5 source files`

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest
```

Expected: `2 passed`

---

### Task 5: Commit

- [ ] **Step 1: Stage and commit**

```bash
git init
git add pyproject.toml uv.lock src/ tests/ docs/ CLAUDE.md README.md
git commit -m "chore: initial project scaffold with uv, src layout, and pipeline skeleton"
```

Expected: commit created with all project files.
