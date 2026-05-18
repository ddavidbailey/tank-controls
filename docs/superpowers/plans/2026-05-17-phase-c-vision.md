# Phase C: Vision Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two-hand camera tracking that maps left-hand position to tank drive keys (W/A/S/D) and right-hand position to turret mouse movement, running concurrently with the Phase B voice pipeline.

**Architecture:** Two new asyncio coroutines (`_vision_stage`, `_gesture_hid_stage`) join the existing `asyncio.gather()`. Frame capture runs in a background thread; MediaPipe runs in the shared `ThreadPoolExecutor`. `GestureHID` holds/releases drive keys and moves the mouse each frame based on wrist position relative to fixed frame-half centres.

**Tech Stack:** `opencv-python`, `mediapipe`, `numpy`, `pynput.mouse`, `asyncio`, `threading`

---

## Before you begin

```bash
git checkout master && git pull origin master
git checkout -b phase-c/vision
```

---

### Task 1: VisionConfig dataclass + `[vision]` section parsing

**Files:**
- Modify: `src/tank_controls/config/loader.py`
- Test: `tests/config/test_loader.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/config/test_loader.py` (keep all existing tests):

```python
from tank_controls.config.loader import VisionConfig


def test_vision_config_defaults_when_section_absent(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text('[profile]\nname = "test"\n')
    config = load_config(cfg)
    assert config.vision.camera_index == 0
    assert config.vision.frame_width == 640
    assert config.vision.frame_height == 480
    assert config.vision.fps == 30
    assert config.vision.quadrant_threshold == 0.1
    assert config.vision.max_mouse_speed == 15


def test_vision_config_values_parsed(tmp_path: Path) -> None:
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        '[profile]\nname = "test"\n'
        "[vision]\ncamera_index = 1\nquadrant_threshold = 0.15\nmax_mouse_speed = 20\n"
    )
    config = load_config(cfg)
    assert config.vision.camera_index == 1
    assert config.vision.quadrant_threshold == 0.15
    assert config.vision.max_mouse_speed == 20
```

- [ ] **Step 2: Run to verify they fail**

```
uv run pytest tests/config/test_loader.py::test_vision_config_defaults_when_section_absent tests/config/test_loader.py::test_vision_config_values_parsed -v
```

Expected: `ImportError` — `VisionConfig` does not exist yet.

- [ ] **Step 3: Add VisionConfig and update Config and load_config**

In `src/tank_controls/config/loader.py`, insert `VisionConfig` before `VoiceConfig`:

```python
@dataclass
class VisionConfig:
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480
    fps: int = 30
    quadrant_threshold: float = 0.1
    max_mouse_speed: int = 15
```

Add `vision` field to the `Config` dataclass (after `voice`):

```python
@dataclass
class Config:
    profile_name: str
    press: dict[str, str] = field(default_factory=dict)
    hold: dict[str, str] = field(default_factory=dict)
    mouse: dict[str, str] = field(default_factory=dict)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
```

Replace the final `return` line in `load_config` with:

```python
    vision_raw: dict[str, Any] = data.get("vision", {})
    vision = VisionConfig(
        camera_index=int(vision_raw.get("camera_index", 0)),
        frame_width=int(vision_raw.get("frame_width", 640)),
        frame_height=int(vision_raw.get("frame_height", 480)),
        fps=int(vision_raw.get("fps", 30)),
        quadrant_threshold=float(vision_raw.get("quadrant_threshold", 0.1)),
        max_mouse_speed=int(vision_raw.get("max_mouse_speed", 15)),
    )
    return Config(
        profile_name=profile_name,
        press=press,
        hold=hold,
        mouse=mouse,
        voice=voice,
        vision=vision,
    )
```

- [ ] **Step 4: Run all loader tests to verify they pass**

```
uv run pytest tests/config/test_loader.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/config/loader.py tests/config/test_loader.py
git commit -m "feat: add VisionConfig dataclass and [vision] section parsing"
```

---

### Task 2: Gesture dataclasses + compute_gesture logic

**Files:**
- Create: `src/tank_controls/vision/gesture.py`
- Create: `tests/vision/__init__.py`
- Create: `tests/vision/test_gesture.py`

- [ ] **Step 1: Create tests/vision package**

```bash
touch tests/vision/__init__.py
```

- [ ] **Step 2: Write failing tests**

Create `tests/vision/test_gesture.py`:

```python
from tank_controls.config.loader import VisionConfig
from tank_controls.vision.gesture import HandState, compute_gesture

CONFIG = VisionConfig(quadrant_threshold=0.1, max_mouse_speed=15)


def test_no_hands_returns_empty_state() -> None:
    state = compute_gesture(HandState(None, None), CONFIG)
    assert state.hold_actions == set()
    assert state.mouse_delta == (0, 0)


def test_left_hand_in_deadzone_no_actions() -> None:
    state = compute_gesture(HandState(left_wrist=(0.25, 0.5), right_wrist=None), CONFIG)
    assert state.hold_actions == set()


def test_left_hand_up_throttle_up() -> None:
    state = compute_gesture(HandState(left_wrist=(0.25, 0.35), right_wrist=None), CONFIG)
    assert "throttle_up" in state.hold_actions
    assert "turn_right" not in state.hold_actions
    assert "turn_left" not in state.hold_actions


def test_left_hand_down_throttle_down() -> None:
    state = compute_gesture(HandState(left_wrist=(0.25, 0.65), right_wrist=None), CONFIG)
    assert "throttle_down" in state.hold_actions


def test_left_hand_right_turn_right() -> None:
    state = compute_gesture(HandState(left_wrist=(0.40, 0.5), right_wrist=None), CONFIG)
    assert "turn_right" in state.hold_actions


def test_left_hand_left_turn_left() -> None:
    state = compute_gesture(HandState(left_wrist=(0.10, 0.5), right_wrist=None), CONFIG)
    assert "turn_left" in state.hold_actions


def test_left_hand_diagonal_up_right() -> None:
    state = compute_gesture(HandState(left_wrist=(0.40, 0.35), right_wrist=None), CONFIG)
    assert state.hold_actions == {"throttle_up", "turn_right"}


def test_left_hand_diagonal_down_left() -> None:
    state = compute_gesture(HandState(left_wrist=(0.10, 0.65), right_wrist=None), CONFIG)
    assert state.hold_actions == {"throttle_down", "turn_left"}


def test_right_hand_in_deadzone_zero_delta() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.75, 0.5)), CONFIG)
    assert state.mouse_delta == (0, 0)


def test_right_hand_right_positive_dx() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.90, 0.5)), CONFIG)
    dx, dy = state.mouse_delta
    assert dx > 0
    assert dy == 0


def test_right_hand_up_negative_dy() -> None:
    # up in image coords = lower y value
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.75, 0.35)), CONFIG)
    dx, dy = state.mouse_delta
    assert dx == 0
    assert dy < 0


def test_right_hand_diagonal_up_right() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.90, 0.35)), CONFIG)
    dx, dy = state.mouse_delta
    assert dx > 0
    assert dy < 0


def test_right_hand_speed_scales_with_distance() -> None:
    near = compute_gesture(HandState(left_wrist=None, right_wrist=(0.82, 0.5)), CONFIG)
    far = compute_gesture(HandState(left_wrist=None, right_wrist=(0.96, 0.5)), CONFIG)
    assert far.mouse_delta[0] > near.mouse_delta[0]


def test_right_hand_absent_zero_delta() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=None), CONFIG)
    assert state.mouse_delta == (0, 0)
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/vision/test_gesture.py -v
```

Expected: `ModuleNotFoundError` — `tank_controls.vision.gesture` does not exist yet.

- [ ] **Step 4: Implement gesture.py**

Create `src/tank_controls/vision/gesture.py`:

```python
from dataclasses import dataclass, field

from tank_controls.config.loader import VisionConfig


@dataclass
class HandState:
    left_wrist: tuple[float, float] | None
    right_wrist: tuple[float, float] | None


@dataclass
class GestureState:
    hold_actions: set[str] = field(default_factory=set)
    mouse_delta: tuple[int, int] = (0, 0)


def compute_gesture(state: HandState, config: VisionConfig) -> GestureState:
    return GestureState(
        hold_actions=_compute_drive(state.left_wrist, config),
        mouse_delta=_compute_turret(state.right_wrist, config),
    )


def _compute_drive(
    wrist: tuple[float, float] | None,
    config: VisionConfig,
) -> set[str]:
    if wrist is None:
        return set()

    dx = wrist[0] - 0.25
    dy = wrist[1] - 0.5  # negative = up in image coords
    t = config.quadrant_threshold

    actions: set[str] = set()
    if dx > t:
        actions.add("turn_right")
    elif dx < -t:
        actions.add("turn_left")
    if dy < -t:
        actions.add("throttle_up")
    elif dy > t:
        actions.add("throttle_down")

    return actions


def _compute_turret(
    wrist: tuple[float, float] | None,
    config: VisionConfig,
) -> tuple[int, int]:
    if wrist is None:
        return (0, 0)

    dx_raw = wrist[0] - 0.75
    dy_raw = wrist[1] - 0.5
    t = config.quadrant_threshold

    mouse_x = 0 if abs(dx_raw) < t else int((dx_raw / 0.5) * config.max_mouse_speed)
    mouse_y = 0 if abs(dy_raw) < t else int((dy_raw / 0.5) * config.max_mouse_speed)

    return (mouse_x, mouse_y)
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/vision/test_gesture.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/vision/gesture.py tests/vision/__init__.py tests/vision/test_gesture.py
git commit -m "feat: add gesture dataclasses and quadrant/turret compute logic"
```

---

### Task 3: GestureHID — key hold/release + mouse movement

**Files:**
- Create: `src/tank_controls/vision/hid.py`
- Create: `tests/vision/test_gesture_hid.py`
- Modify: `tests/conftest.py` — add `pynput.mouse` mock

- [ ] **Step 1: Add pynput.mouse to conftest mock**

In `tests/conftest.py`, add after the existing pynput mock lines:

```python
sys.modules["pynput.mouse"] = pynput_mock.mouse
```

- [ ] **Step 2: Write failing tests**

Create `tests/vision/test_gesture_hid.py`:

```python
from unittest.mock import patch

from tank_controls.vision.gesture import GestureState
from tank_controls.vision.hid import GestureHID


def test_new_action_presses_key() -> None:
    with patch("tank_controls.vision.hid.KeyboardController") as MockKbd, \
         patch("tank_controls.vision.hid.MouseController"):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        kbd.press.assert_called_with("w")


def test_dropped_action_releases_key() -> None:
    with patch("tank_controls.vision.hid.KeyboardController") as MockKbd, \
         patch("tank_controls.vision.hid.MouseController"):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(0, 0)))
        kbd.release.assert_called_with("w")


def test_mouse_delta_applied() -> None:
    with patch("tank_controls.vision.hid.KeyboardController"), \
         patch("tank_controls.vision.hid.MouseController") as MockMouse:
        mouse = MockMouse.return_value
        hid = GestureHID(hold_bindings={})
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(5, -3)))
        mouse.move.assert_called_once_with(5, -3)


def test_zero_mouse_delta_not_applied() -> None:
    with patch("tank_controls.vision.hid.KeyboardController"), \
         patch("tank_controls.vision.hid.MouseController") as MockMouse:
        mouse = MockMouse.return_value
        hid = GestureHID(hold_bindings={})
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(0, 0)))
        mouse.move.assert_not_called()


def test_release_all_releases_held_keys() -> None:
    with patch("tank_controls.vision.hid.KeyboardController") as MockKbd, \
         patch("tank_controls.vision.hid.MouseController"):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        hid.release_all()
        kbd.release.assert_called_with("w")
```

- [ ] **Step 3: Run to verify they fail**

```
uv run pytest tests/vision/test_gesture_hid.py -v
```

Expected: `ModuleNotFoundError` — `tank_controls.vision.hid` does not exist yet.

- [ ] **Step 4: Implement vision/hid.py**

Create `src/tank_controls/vision/hid.py`:

```python
import logging

from pynput.keyboard import Controller as KeyboardController, Key  # type: ignore[import-untyped]
from pynput.mouse import Controller as MouseController  # type: ignore[import-untyped]

from tank_controls.vision.gesture import GestureState

logger = logging.getLogger(__name__)

_MODIFIER_MAP: dict[str, Key] = {
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}

_SPECIAL_KEY_MAP: dict[str, Key] = {
    "space": Key.space,
    "enter": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)},
}


def _parse_binding(binding: str) -> tuple[list[Key], Key | str]:
    parts = binding.split("+")
    modifiers = [_MODIFIER_MAP[p] for p in parts[:-1] if p in _MODIFIER_MAP]
    key_str = parts[-1]
    return modifiers, _SPECIAL_KEY_MAP.get(key_str, key_str)


class GestureHID:
    def __init__(self, hold_bindings: dict[str, str]) -> None:
        self._keyboard = KeyboardController()
        self._mouse = MouseController()
        self._hold_bindings = hold_bindings
        self._held: set[str] = set()

    def apply(self, state: GestureState) -> None:
        for action in self._held - state.hold_actions:
            self._release(action)
        for action in state.hold_actions - self._held:
            self._press(action)
        self._held = set(state.hold_actions)

        dx, dy = state.mouse_delta
        if dx != 0 or dy != 0:
            try:
                self._mouse.move(dx, dy)
            except Exception:
                logger.warning(
                    "Mouse move failed — check Accessibility in System Settings."
                )

    def release_all(self) -> None:
        for action in list(self._held):
            self._release(action)
        self._held = set()

    def _press(self, action: str) -> None:
        binding = self._hold_bindings.get(action, "")
        if not binding:
            return
        modifiers, key = _parse_binding(binding)
        try:
            for mod in modifiers:
                self._keyboard.press(mod)
            self._keyboard.press(key)
        except Exception:
            logger.warning(
                "Key press failed for '%s' — check Accessibility in System Settings.", binding
            )

    def _release(self, action: str) -> None:
        binding = self._hold_bindings.get(action, "")
        if not binding:
            return
        modifiers, key = _parse_binding(binding)
        try:
            self._keyboard.release(key)
            for mod in reversed(modifiers):
                self._keyboard.release(mod)
        except Exception:
            logger.warning("Key release failed for '%s'.", binding)
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run pytest tests/vision/test_gesture_hid.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run full suite to check for regressions**

```
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/tank_controls/vision/hid.py tests/vision/test_gesture_hid.py tests/conftest.py
git commit -m "feat: add GestureHID for sustained key hold and turret mouse movement"
```

---

### Task 4: Frame capture

**Files:**
- Create: `src/tank_controls/vision/capture.py`

No unit tests — hardware-dependent. Verified in the pipeline smoke test (Task 6).

- [ ] **Step 1: Implement FrameCapture**

Create `src/tank_controls/vision/capture.py`:

```python
import asyncio
import logging
import threading
from typing import Any

import cv2  # type: ignore[import-untyped]
import numpy as np

from tank_controls.config.loader import VisionConfig

logger = logging.getLogger(__name__)


class FrameCapture:
    def __init__(
        self,
        queue: asyncio.Queue[Any],
        loop: asyncio.AbstractEventLoop,
        config: VisionConfig,
    ) -> None:
        self._queue = queue
        self._loop = loop
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        cap = cv2.VideoCapture(self._config.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera index {self._config.camera_index}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.frame_height)
        cap.set(cv2.CAP_PROP_FPS, self._config.fps)
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop, args=(cap,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _put_frame(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass  # drop stale frame; fresh frames are always preferred

    def _capture_loop(self, cap: cv2.VideoCapture) -> None:
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._loop.call_soon_threadsafe(self._put_frame, frame_rgb)
        finally:
            cap.release()
```

- [ ] **Step 2: Verify import is clean**

```
uv run python -c "from tank_controls.vision.capture import FrameCapture; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add src/tank_controls/vision/capture.py
git commit -m "feat: add OpenCV FrameCapture with background thread"
```

---

### Task 5: Hand landmark detection

**Files:**
- Create: `src/tank_controls/vision/landmarks.py`
- Modify: `tests/conftest.py` — add `cv2` and `mediapipe` mocks

No unit tests — hardware-dependent. Verified in the pipeline smoke test (Task 6).

- [ ] **Step 1: Add cv2 and mediapipe mocks to conftest**

In `tests/conftest.py`, add after the existing mock lines:

```python
sys.modules["cv2"] = MagicMock()
sys.modules["mediapipe"] = MagicMock()
```

- [ ] **Step 2: Implement HandLandmarker**

Create `src/tank_controls/vision/landmarks.py`:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import mediapipe as mp  # type: ignore[import-untyped]
import numpy as np

from tank_controls.vision.gesture import HandState


class HandLandmarker:
    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self._executor = executor
        mp_hands: Any = mp.solutions.hands
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )

    async def detect(self, frame: np.ndarray) -> HandState:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._detect_sync, frame)

    def _detect_sync(self, frame: np.ndarray) -> HandState:
        results = self._hands.process(frame)
        left_wrist: tuple[float, float] | None = None
        right_wrist: tuple[float, float] | None = None

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                wrist = hand_landmarks.landmark[0]
                # Assign by frame position: left half = drive, right half = turret
                if wrist.x < 0.5:
                    left_wrist = (float(wrist.x), float(wrist.y))
                else:
                    right_wrist = (float(wrist.x), float(wrist.y))

        return HandState(left_wrist=left_wrist, right_wrist=right_wrist)

    def close(self) -> None:
        self._hands.close()
```

- [ ] **Step 3: Verify import is clean**

```
uv run python -c "from tank_controls.vision.landmarks import HandLandmarker; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Run full test suite to verify conftest mocks don't break anything**

```
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/vision/landmarks.py tests/conftest.py
git commit -m "feat: add MediaPipe HandLandmarker wrapper with frame-position hand assignment"
```

---

### Task 6: Pipeline wiring

**Files:**
- Modify: `src/tank_controls/main.py`

- [ ] **Step 1: Replace main.py with vision-integrated pipeline**

Full replacement of `src/tank_controls/main.py`:

```python
import argparse
import asyncio
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import sounddevice as sd  # type: ignore[import-untyped]

from tank_controls.audio.capture import AudioCapture
from tank_controls.audio.intent import match_intent
from tank_controls.audio.stt import SpeechToText
from tank_controls.audio.vad import VoiceActivityDetector
from tank_controls.config.errors import ConfigError
from tank_controls.config.loader import Config, VisionConfig, load_config
from tank_controls.hid.dry_run import log_action
from tank_controls.hid.output import KeyPresser
from tank_controls.vision.capture import FrameCapture
from tank_controls.vision.gesture import GestureState, compute_gesture
from tank_controls.vision.hid import GestureHID
from tank_controls.vision.landmarks import HandLandmarker

_QUEUE_DEPTH = 5


async def _vad_stage(
    raw_queue: asyncio.Queue[bytes],
    speech_queue: asyncio.Queue[list[bytes]],
    vad: VoiceActivityDetector,
) -> None:
    while True:
        frame = await raw_queue.get()
        utterance = vad.process_frame(frame)
        if utterance is not None:
            try:
                speech_queue.put_nowait(utterance)
            except asyncio.QueueFull:
                logging.warning("speech_queue full — utterance dropped")


async def _stt_stage(
    speech_queue: asyncio.Queue[list[bytes]],
    intent_queue: asyncio.Queue[tuple[str, str]],
    stt: SpeechToText,
    press: dict[str, str],
    threshold: float,
) -> None:
    while True:
        frames = await speech_queue.get()
        text = await stt.transcribe(frames)
        if not text:
            continue
        logging.debug("Transcribed: %r", text)
        result = match_intent(text, press, threshold)
        if result is not None:
            try:
                intent_queue.put_nowait(result)
            except asyncio.QueueFull:
                logging.warning("intent_queue full — intent dropped")


async def _hid_stage(
    intent_queue: asyncio.Queue[tuple[str, str]],
    presser: KeyPresser,
) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        presser.press(action_name, binding)


async def _dry_run_stage(intent_queue: asyncio.Queue[tuple[str, str]]) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        log_action(action_name, "press", binding)


async def _vision_stage(
    frame_queue: asyncio.Queue[Any],
    gesture_queue: asyncio.Queue[GestureState],
    landmarker: HandLandmarker,
    vision_config: VisionConfig,
) -> None:
    while True:
        frame = await frame_queue.get()
        hand_state = await landmarker.detect(frame)
        state = compute_gesture(hand_state, vision_config)
        try:
            gesture_queue.put_nowait(state)
        except asyncio.QueueFull:
            pass


async def _gesture_hid_stage(
    gesture_queue: asyncio.Queue[GestureState],
    hid: GestureHID,
) -> None:
    while True:
        state = await gesture_queue.get()
        hid.apply(state)


async def _run_pipeline(config: Config, dry_run: bool) -> None:
    # Voice queues
    raw_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    speech_queue: asyncio.Queue[list[bytes]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    intent_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=_QUEUE_DEPTH)
    # Vision queues
    frame_queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=2)
    gesture_queue: asyncio.Queue[GestureState] = asyncio.Queue(maxsize=_QUEUE_DEPTH)

    vad = VoiceActivityDetector(config.voice.energy_threshold)
    loop = asyncio.get_running_loop()
    audio_capture = AudioCapture(raw_queue, loop)
    initial_prompt = ", ".join(k.replace("_", " ") for k in config.press)

    cam_capture = FrameCapture(frame_queue, loop, config.vision)
    gesture_hid = GestureHID(config.hold)

    try:
        cam_capture.start()
    except RuntimeError as e:
        logging.error("Could not open camera: %s", e)
        sys.exit(1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        stt = SpeechToText(str(config.voice.model), executor, initial_prompt=initial_prompt)
        landmarker = HandLandmarker(executor)
        try:
            stream = audio_capture.start()
        except sd.PortAudioError as e:
            logging.error("Could not open microphone: %s", e)
            cam_capture.stop()
            sys.exit(1)
        try:
            hid_coro = (
                _dry_run_stage(intent_queue)
                if dry_run
                else _hid_stage(intent_queue, KeyPresser(config.voice.action_cooldown_ms))
            )
            await asyncio.gather(
                _vad_stage(raw_queue, speech_queue, vad),
                _stt_stage(
                    speech_queue, intent_queue, stt, config.press, config.voice.match_threshold
                ),
                hid_coro,
                _vision_stage(frame_queue, gesture_queue, landmarker, config.vision),
                _gesture_hid_stage(gesture_queue, gesture_hid),
            )
        finally:
            stream.stop()
            stream.close()
            cam_capture.stop()
            landmarker.close()
            gesture_hid.release_all()


def main() -> None:
    parser = argparse.ArgumentParser(description="War Thunder multimodal controls")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="Path to keybind config file (default: config.toml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log recognised voice actions instead of sending keypresses",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as e:
        logging.error(str(e))
        sys.exit(1)

    logging.info("Loaded profile: %s", config.profile_name)
    logging.info(
        "Listening for: %s",
        ", ".join(k.replace("_", " ") for k in config.press),
    )

    try:
        asyncio.run(_run_pipeline(config, args.dry_run))
    except KeyboardInterrupt:
        logging.info("Stopped.")
    except Exception as e:
        logging.error("Fatal error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```
uv run pytest -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run ruff and mypy**

```
uv run ruff check . && uv run ruff format --check . && uv run mypy src/
```

Expected: no errors.

- [ ] **Step 4: Smoke test**

```
uv run tank-controls --dry-run
```

Expected: program starts, logs `Loaded profile` and `Listening for`, no import errors. Camera opens. Ctrl+C to stop.

- [ ] **Step 5: Commit**

```bash
git add src/tank_controls/main.py
git commit -m "feat: wire vision pipeline into asyncio gather alongside voice"
```

- [ ] **Step 6: Push branch**

```bash
git push -u origin phase-c/vision
```
