# Phase D: Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global `~` panic-disable hotkey that pauses all HID output and releases held keys, plus optional `--log-feedback` and `--overlay-feedback` CLI flags for state visibility.

**Architecture:** A `PanicGate` (threading.Event + pynput GlobalHotKeys) gates both HID stages. A `FeedbackEmitter` logs and/or pushes frames to a display queue. The overlay window is a second cv2 window in the main display thread showing the zone overlay and LIVE/PAUSED status. Zone-drawing logic is extracted into a shared `_draw_zones()` helper to avoid duplication between the debug and overlay renderers.

**Tech Stack:** Python 3.11+, pynput (GlobalHotKeys), threading.Event, cv2, asyncio, existing pipeline in `main.py`.

---

## File Map

| File | What changes |
|------|-------------|
| `src/tank_controls/hid/panic.py` | **New** — `PanicGate` |
| `src/tank_controls/hid/feedback.py` | **New** — `FeedbackEmitter` |
| `src/tank_controls/hid/output.py` | Add optional `gate` param to `KeyPresser.press()` |
| `src/tank_controls/vision/hid.py` | Add optional `feedback` param to `GestureHID.__init__`; emit on hold change in `apply()` |
| `src/tank_controls/vision/debug.py` | Extract `_draw_zones()`; add `draw_overlay_feedback()` |
| `src/tank_controls/main.py` | New flags; wire gate + emitter; overlay display queue |
| `tests/hid/test_panic.py` | **New** — PanicGate tests |
| `tests/hid/test_feedback.py` | **New** — FeedbackEmitter tests |
| `tests/hid/test_output.py` | Two new gate-gating tests |
| `tests/vision/test_gesture_hid.py` | Two new feedback emission tests |

---

### Task 1: PanicGate

**Files:**
- Create: `src/tank_controls/hid/panic.py`
- Create: `tests/hid/test_panic.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/hid/test_panic.py
from unittest.mock import MagicMock

from tank_controls.hid.panic import PanicGate


def _make_gate() -> tuple[PanicGate, MagicMock, MagicMock]:
    release_fn = MagicMock()
    on_toggle = MagicMock()
    return PanicGate(release_fn=release_fn, on_toggle=on_toggle), release_fn, on_toggle


def test_initially_not_paused() -> None:
    gate, _, _ = _make_gate()
    assert gate.is_paused() is False


def test_toggle_pauses() -> None:
    gate, _, _ = _make_gate()
    gate._on_hotkey()
    assert gate.is_paused() is True


def test_toggle_twice_resumes() -> None:
    gate, _, _ = _make_gate()
    gate._on_hotkey()
    gate._on_hotkey()
    assert gate.is_paused() is False


def test_release_fn_called_on_pause() -> None:
    gate, release_fn, _ = _make_gate()
    gate._on_hotkey()
    release_fn.assert_called_once()


def test_release_fn_not_called_on_resume() -> None:
    gate, release_fn, _ = _make_gate()
    gate._on_hotkey()
    release_fn.reset_mock()
    gate._on_hotkey()
    release_fn.assert_not_called()


def test_on_toggle_called_with_true_on_pause() -> None:
    gate, _, on_toggle = _make_gate()
    gate._on_hotkey()
    on_toggle.assert_called_once_with(True)


def test_on_toggle_called_with_false_on_resume() -> None:
    gate, _, on_toggle = _make_gate()
    gate._on_hotkey()
    on_toggle.reset_mock()
    gate._on_hotkey()
    on_toggle.assert_called_once_with(False)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/hid/test_panic.py -v
```
Expected: `ModuleNotFoundError` for `tank_controls.hid.panic`.

- [ ] **Step 3: Implement PanicGate**

```python
# src/tank_controls/hid/panic.py
import threading
from collections.abc import Callable

from pynput.keyboard import GlobalHotKeys  # type: ignore[import-untyped]


class PanicGate:
    def __init__(
        self,
        release_fn: Callable[[], None],
        on_toggle: Callable[[bool], None],
    ) -> None:
        self._paused = threading.Event()
        self._release_fn = release_fn
        self._on_toggle = on_toggle
        self._listener: GlobalHotKeys | None = None

    def start(self) -> None:
        self._listener = GlobalHotKeys({"<shift>+`": self._on_hotkey})
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener.join(timeout=1.0)
            self._listener = None

    def is_paused(self) -> bool:
        return self._paused.is_set()

    def _on_hotkey(self) -> None:
        if self._paused.is_set():
            self._paused.clear()
            self._on_toggle(False)
        else:
            self._paused.set()
            self._release_fn()
            self._on_toggle(True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hid/test_panic.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Check types and lint**

```bash
uv run ruff check . && uv run mypy src/
```
Expected: `All checks passed!` and `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/hid/panic.py tests/hid/test_panic.py
git commit -m "feat: add PanicGate with global Shift+\` toggle hotkey"
```

---

### Task 2: FeedbackEmitter

**Files:**
- Create: `src/tank_controls/hid/feedback.py`
- Create: `tests/hid/test_feedback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/hid/test_feedback.py
import logging
import queue as _tq

from tank_controls.hid.feedback import FeedbackEmitter
from tank_controls.vision.gesture import GestureState


def test_emit_toggle_paused_logs(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(True)
    assert "[PAUSED]" in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_resumed_logs(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(False)
    assert "[RESUMED]" in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_no_log_when_disabled(caplog: object) -> None:
    emitter = FeedbackEmitter(log=False)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(True)
    assert "[PAUSED]" not in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_pushes_to_queue() -> None:
    q: _tq.Queue[object] = _tq.Queue()
    emitter = FeedbackEmitter(log=False, display_queue=q)
    emitter.emit_toggle(True)
    assert q.get_nowait() == {"paused": True}


def test_emit_gesture_logs_actions(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    state = GestureState(hold_actions={"throttle_up", "turn_right"})
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_gesture(state)
    assert "Drive:" in caplog.text  # type: ignore[union-attr]


def test_emit_gesture_no_log_when_empty(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    state = GestureState(hold_actions=set())
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_gesture(state)
    assert "Drive:" not in caplog.text  # type: ignore[union-attr]


def test_emit_gesture_pushes_to_queue() -> None:
    q: _tq.Queue[object] = _tq.Queue()
    emitter = FeedbackEmitter(log=False, display_queue=q)
    state = GestureState(hold_actions={"throttle_up"})
    emitter.emit_gesture(state)
    msg = q.get_nowait()
    assert msg == {"state": state}  # type: ignore[comparison-overlap]


def test_queue_full_does_not_raise() -> None:
    q: _tq.Queue[object] = _tq.Queue(maxsize=1)
    q.put_nowait({"paused": True})
    emitter = FeedbackEmitter(log=False, display_queue=q)
    emitter.emit_toggle(False)  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/hid/test_feedback.py -v
```
Expected: `ModuleNotFoundError` for `tank_controls.hid.feedback`.

- [ ] **Step 3: Implement FeedbackEmitter**

```python
# src/tank_controls/hid/feedback.py
import logging
import queue as _tq
from typing import Any

from tank_controls.vision.gesture import GestureState

logger = logging.getLogger(__name__)


class FeedbackEmitter:
    def __init__(
        self,
        log: bool = False,
        display_queue: "_tq.Queue[Any] | None" = None,
    ) -> None:
        self._log = log
        self._display_queue = display_queue

    def emit_toggle(self, paused: bool) -> None:
        if self._log:
            logger.info("[PAUSED]" if paused else "[RESUMED]")
        if self._display_queue is not None:
            try:
                self._display_queue.put_nowait({"paused": paused})
            except _tq.Full:
                pass

    def emit_gesture(self, state: GestureState) -> None:
        if self._log and state.hold_actions:
            logger.info("Drive: %s", " + ".join(sorted(state.hold_actions)))
        if self._display_queue is not None:
            try:
                self._display_queue.put_nowait({"state": state})
            except _tq.Full:
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/hid/test_feedback.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Check types and lint**

```bash
uv run ruff check . && uv run mypy src/
```
Expected: all clear.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/hid/feedback.py tests/hid/test_feedback.py
git commit -m "feat: add FeedbackEmitter for log and overlay state feedback"
```

---

### Task 3: KeyPresser gate integration

**Files:**
- Modify: `src/tank_controls/hid/output.py`
- Modify: `tests/hid/test_output.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/hid/test_output.py`:

```python
def test_press_blocked_when_gate_paused() -> None:
    from unittest.mock import MagicMock

    gate = MagicMock()
    gate.is_paused.return_value = True
    with patch("tank_controls.hid.output.Controller"):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space", gate=gate)
    assert result is False


def test_press_allowed_when_gate_live() -> None:
    from unittest.mock import MagicMock

    gate = MagicMock()
    gate.is_paused.return_value = False
    with patch("tank_controls.hid.output.Controller"):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space", gate=gate)
    assert result is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/hid/test_output.py::test_press_blocked_when_gate_paused tests/hid/test_output.py::test_press_allowed_when_gate_live -v
```
Expected: `TypeError` (unexpected keyword argument `gate`).

- [ ] **Step 3: Update KeyPresser.press() in output.py**

Add these imports at the top of `src/tank_controls/hid/output.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tank_controls.hid.panic import PanicGate
```

Update the `press` method signature (keep the body identical, just add the gate check at the top):

```python
    def press(
        self, action_name: str, binding: str, gate: "PanicGate | None" = None
    ) -> bool:
        if gate is not None and gate.is_paused():
            return False
        now = time.monotonic()
        if action_name in self._last_fired:
            if (now - self._last_fired[action_name]) * 1000 < self._cooldown_ms:
                return False
        self._last_fired[action_name] = now

        modifiers, key = self._parse_binding(binding)
        try:
            for mod in modifiers:
                self._controller.press(mod)
            self._controller.press(key)
            self._controller.release(key)
            for mod in reversed(modifiers):
                self._controller.release(mod)
        except Exception:
            logger.warning(
                "Failed to press '%s'. "
                "Grant Accessibility access in System Settings → Privacy & Security.",
                binding,
            )
            return False
        return True
```

- [ ] **Step 4: Run all output tests to verify they pass**

```bash
uv run pytest tests/hid/test_output.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Check types and lint**

```bash
uv run ruff check . && uv run mypy src/
```
Expected: all clear.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/hid/output.py tests/hid/test_output.py
git commit -m "feat: gate KeyPresser.press() behind PanicGate when provided"
```

---

### Task 4: GestureHID feedback integration

**Files:**
- Modify: `src/tank_controls/vision/hid.py`
- Modify: `tests/vision/test_gesture_hid.py`

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `tests/vision/test_gesture_hid.py`:

```python
def test_feedback_emitted_on_hold_actions_change() -> None:
    from unittest.mock import MagicMock

    feedback = MagicMock()
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
    ):
        hid = GestureHID(hold_bindings={"throttle_up": "w"}, feedback=feedback)
        state = GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0))
        hid.apply(state)
    feedback.emit_gesture.assert_called_once_with(state)


def test_feedback_not_emitted_when_actions_unchanged() -> None:
    from unittest.mock import MagicMock

    feedback = MagicMock()
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
    ):
        hid = GestureHID(hold_bindings={"throttle_up": "w"}, feedback=feedback)
        state = GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0))
        hid.apply(state)
        feedback.reset_mock()
        hid.apply(state)  # same hold_actions — no change
    feedback.emit_gesture.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/vision/test_gesture_hid.py::test_feedback_emitted_on_hold_actions_change tests/vision/test_gesture_hid.py::test_feedback_not_emitted_when_actions_unchanged -v
```
Expected: `TypeError` (unexpected keyword argument `feedback`).

- [ ] **Step 3: Update GestureHID in vision/hid.py**

Add these imports at the top of `src/tank_controls/vision/hid.py`:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tank_controls.hid.feedback import FeedbackEmitter
```

Update `__init__` and `apply()` — replace the full class with:

```python
class GestureHID:
    def __init__(
        self,
        hold_bindings: dict[str, str],
        feedback: "FeedbackEmitter | None" = None,
    ) -> None:
        self._keyboard = KeyboardController()
        self._mouse = MouseController()
        self._hold_bindings = hold_bindings
        self._held: set[str] = set()
        self._feedback = feedback

    def apply(self, state: GestureState) -> None:
        prev_held = set(self._held)

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
                logger.warning("Mouse move failed — check Accessibility in System Settings.")

        if self._feedback is not None and self._held != prev_held:
            self._feedback.emit_gesture(state)

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

- [ ] **Step 4: Run all gesture_hid tests to verify they pass**

```bash
uv run pytest tests/vision/test_gesture_hid.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Check types and lint**

```bash
uv run ruff check . && uv run mypy src/
```
Expected: all clear.

- [ ] **Step 6: Commit**

```bash
git add src/tank_controls/vision/hid.py tests/vision/test_gesture_hid.py
git commit -m "feat: emit feedback from GestureHID when hold_actions change"
```

---

### Task 5: Overlay feedback rendering in debug.py

**Files:**
- Modify: `src/tank_controls/vision/debug.py`

- [ ] **Step 1: Rewrite debug.py**

Replace the entire contents of `src/tank_controls/vision/debug.py` with:

```python
import cv2
import numpy as np

from tank_controls.config.loader import VisionConfig
from tank_controls.vision.gesture import GestureState, HandState

_GREEN = (0, 220, 0)
_ORANGE = (0, 140, 255)


def _draw_zones(overlay: np.ndarray, config: VisionConfig) -> None:
    """Draw zone lines, labels, centre dots, and dividing line in-place."""
    h, w = overlay.shape[:2]
    tx = int(w * config.quadrant_threshold)
    ty = int(h * config.quadrant_threshold)
    mid = w // 2
    cy = int(h * 0.5)
    cx_l = int(w * 0.25)
    cx_r = int(w * 0.75)

    # Left half — drive zones (green)
    cv2.line(overlay, (cx_l - tx, 0), (cx_l - tx, h), _GREEN, 1)
    cv2.line(overlay, (cx_l + tx, 0), (cx_l + tx, h), _GREEN, 1)
    cv2.line(overlay, (0, cy - ty), (mid, cy - ty), _GREEN, 1)
    cv2.line(overlay, (0, cy + ty), (mid, cy + ty), _GREEN, 1)
    cv2.putText(overlay, "W+A", (10, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "W", (cx_l - 10, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(
        overlay, "W+D", (cx_l + tx + 4, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1
    )
    cv2.putText(overlay, "A", (10, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "D", (cx_l + tx + 4, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "S+A", (10, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "S", (cx_l - 10, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(
        overlay, "S+D", (cx_l + tx + 4, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1
    )
    cv2.circle(overlay, (cx_l, cy), 6, _GREEN, -1)

    # Right half — turret zones (orange)
    cv2.line(overlay, (cx_r - tx, 0), (cx_r - tx, h), _ORANGE, 1)
    cv2.line(overlay, (cx_r + tx, 0), (cx_r + tx, h), _ORANGE, 1)
    cv2.line(overlay, (mid, cy - ty), (w, cy - ty), _ORANGE, 1)
    cv2.line(overlay, (mid, cy + ty), (w, cy + ty), _ORANGE, 1)
    cv2.circle(overlay, (cx_r, cy), 6, _ORANGE, -1)

    # Dividing line
    cv2.line(overlay, (mid, 0), (mid, h), (200, 200, 200), 2)

    # Half labels
    cv2.putText(
        overlay, "DRIVE  (left hand)", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _GREEN, 1
    )
    cv2.putText(
        overlay, "TURRET  (right hand)", (mid + 8, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, _ORANGE, 1,
    )


def draw_debug_overlay(
    frame: np.ndarray,
    hand_state: HandState,
    gesture_state: GestureState,
    config: VisionConfig,
) -> np.ndarray:
    """Draw zone overlay plus wrist positions and active action labels (debug mode)."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    _draw_zones(overlay, config)

    # Wrist tracking circles
    if hand_state.right_wrist:
        rx = int(hand_state.right_wrist[0] * w)
        ry = int(hand_state.right_wrist[1] * h)
        cv2.circle(overlay, (rx, ry), 18, _GREEN, 3)
        cv2.putText(
            overlay, "DRIVE", (rx + 22, ry + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _GREEN, 2
        )

    if hand_state.left_wrist:
        lx = int(hand_state.left_wrist[0] * w)
        ly = int(hand_state.left_wrist[1] * h)
        cv2.circle(overlay, (lx, ly), 18, _ORANGE, 3)
        cv2.putText(
            overlay, "TURRET", (lx + 22, ly + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _ORANGE, 2
        )

    # Active action labels
    y = 26
    if gesture_state.hold_actions:
        text = "Drive: " + " + ".join(sorted(gesture_state.hold_actions))
        cv2.putText(overlay, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, _GREEN, 2)
        y += 28
    if gesture_state.mouse_delta != (0, 0):
        dx, dy = gesture_state.mouse_delta
        cv2.putText(
            overlay, f"Turret: dx={dx:+d} dy={dy:+d}", (10, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, _ORANGE, 2,
        )

    return overlay


def draw_overlay_feedback(
    frame: np.ndarray,
    config: VisionConfig,
    paused: bool,
) -> np.ndarray:
    """Draw zone overlay plus LIVE/PAUSED indicator (overlay-feedback mode)."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    _draw_zones(overlay, config)

    # LIVE / PAUSED indicator — top-right corner
    status_text = "● PAUSED" if paused else "● LIVE"
    status_color = (0, 0, 200) if paused else (0, 200, 0)
    (text_w, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    cv2.putText(
        overlay, status_text, (w - text_w - 12, 32),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2,
    )

    return overlay
```

- [ ] **Step 2: Run full test suite**

```bash
uv run ruff check . && uv run mypy src/ && uv run pytest
```
Expected: all checks pass, 70 tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/tank_controls/vision/debug.py
git commit -m "refactor: extract _draw_zones helper; add draw_overlay_feedback"
```

---

### Task 6: Wire everything in main.py

**Files:**
- Modify: `src/tank_controls/main.py`

This task updates `main.py` in four parts: new imports, updated stage coroutines, updated `_run_pipeline`, and updated `main()`.

- [ ] **Step 1: Replace the full contents of main.py**

```python
import argparse
import asyncio
import logging
import queue as _tq
import sys
import threading
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
from tank_controls.hid.feedback import FeedbackEmitter
from tank_controls.hid.output import KeyPresser
from tank_controls.hid.panic import PanicGate
from tank_controls.vision.capture import FrameCapture
from tank_controls.vision.debug import draw_debug_overlay, draw_overlay_feedback
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
    gate: "PanicGate | None" = None,
) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        presser.press(action_name, binding, gate)


async def _dry_run_stage(intent_queue: asyncio.Queue[tuple[str, str]]) -> None:
    while True:
        action_name, binding = await intent_queue.get()
        log_action(action_name, "press", binding)


async def _dry_run_gesture_stage(gesture_queue: asyncio.Queue[GestureState]) -> None:
    while True:
        state = await gesture_queue.get()
        if state.hold_actions:
            logging.info("[DRY-RUN] gesture: hold %s", sorted(state.hold_actions))
        if state.mouse_delta != (0, 0):
            logging.info("[DRY-RUN] gesture: mouse_move %s", state.mouse_delta)


async def _vision_stage(
    frame_queue: asyncio.Queue[Any],
    gesture_queue: asyncio.Queue[GestureState],
    landmarker: HandLandmarker,
    vision_config: VisionConfig,
    display_queue: "_tq.Queue[Any] | None" = None,
    overlay_queue: "_tq.Queue[Any] | None" = None,
    gate: "PanicGate | None" = None,
) -> None:
    while True:
        frame = await frame_queue.get()
        hand_state = await landmarker.detect(frame)
        state = compute_gesture(hand_state, vision_config)
        try:
            gesture_queue.put_nowait(state)
        except asyncio.QueueFull:
            pass
        if display_queue is not None:
            import cv2

            overlay = draw_debug_overlay(frame, hand_state, state, vision_config)
            bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            try:
                display_queue.put_nowait(bgr)
            except _tq.Full:
                pass
        if overlay_queue is not None:
            import cv2

            paused = gate.is_paused() if gate is not None else False
            overlay = draw_overlay_feedback(frame, vision_config, paused)
            bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            try:
                overlay_queue.put_nowait(bgr)
            except _tq.Full:
                pass


async def _gesture_hid_stage(
    gesture_queue: asyncio.Queue[GestureState],
    hid: GestureHID,
    gate: "PanicGate | None" = None,
) -> None:
    while True:
        state = await gesture_queue.get()
        if gate is not None and gate.is_paused():
            hid.release_all()
        else:
            hid.apply(state)


async def _run_pipeline(
    config: Config,
    dry_run: bool,
    display_queue: "_tq.Queue[Any] | None" = None,
    overlay_queue: "_tq.Queue[Any] | None" = None,
    feedback: "FeedbackEmitter | None" = None,
) -> None:
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
    gesture_hid = GestureHID(config.hold, feedback=feedback)
    gate = PanicGate(
        release_fn=gesture_hid.release_all,
        on_toggle=feedback.emit_toggle if feedback is not None else lambda _: None,
    )

    try:
        cam_capture.start()
    except RuntimeError as e:
        logging.error("Could not open camera: %s", e)
        sys.exit(1)

    gate.start()

    with ThreadPoolExecutor(max_workers=2) as executor:
        stt = SpeechToText(str(config.voice.model), executor, initial_prompt=initial_prompt)
        landmarker = HandLandmarker(executor)
        try:
            stream = audio_capture.start()
        except sd.PortAudioError as e:
            logging.error("Could not open microphone: %s", e)
            cam_capture.stop()
            gate.stop()
            sys.exit(1)
        try:
            hid_coro = (
                _dry_run_stage(intent_queue)
                if dry_run
                else _hid_stage(intent_queue, KeyPresser(config.voice.action_cooldown_ms), gate)
            )
            gesture_hid_coro = (
                _dry_run_gesture_stage(gesture_queue)
                if dry_run
                else _gesture_hid_stage(gesture_queue, gesture_hid, gate)
            )
            await asyncio.gather(
                _vad_stage(raw_queue, speech_queue, vad),
                _stt_stage(
                    speech_queue, intent_queue, stt, config.press, config.voice.match_threshold
                ),
                hid_coro,
                _vision_stage(
                    frame_queue, gesture_queue, landmarker, config.vision,
                    display_queue, overlay_queue, gate,
                ),
                gesture_hid_coro,
            )
        finally:
            stream.stop()
            stream.close()
            cam_capture.stop()
            landmarker.close()
            gesture_hid.release_all()
            gate.stop()


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show camera feed with full diagnostic overlay",
    )
    parser.add_argument(
        "--log-feedback",
        action="store_true",
        help="Log pause/resume and drive action changes to the terminal",
    )
    parser.add_argument(
        "--overlay-feedback",
        action="store_true",
        help="Show camera window with zone overlay and LIVE/PAUSED status",
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

    needs_display = args.debug or args.overlay_feedback

    overlay_q: _tq.Queue[Any] | None = (
        _tq.Queue(maxsize=2) if args.overlay_feedback else None
    )
    emitter: FeedbackEmitter | None = (
        FeedbackEmitter(log=args.log_feedback, display_queue=overlay_q)
        if (args.log_feedback or args.overlay_feedback)
        else None
    )

    if needs_display:
        import cv2

        debug_q: _tq.Queue[Any] = _tq.Queue(maxsize=2)
        exc_holder: list[BaseException] = []

        def _run_in_thread() -> None:
            try:
                asyncio.run(
                    _run_pipeline(
                        config,
                        args.dry_run,
                        display_queue=debug_q if args.debug else None,
                        overlay_queue=overlay_q,
                        feedback=emitter,
                    )
                )
            except KeyboardInterrupt:
                pass
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()

        if args.debug:
            cv2.namedWindow("Tank Controls — Debug", cv2.WINDOW_AUTOSIZE)
        if args.overlay_feedback:
            cv2.namedWindow("Tank Controls — Overlay", cv2.WINDOW_AUTOSIZE)

        try:
            while t.is_alive():
                if args.debug:
                    try:
                        bgr = debug_q.get_nowait()
                        cv2.imshow("Tank Controls — Debug", bgr)
                    except _tq.Empty:
                        pass
                if args.overlay_feedback and overlay_q is not None:
                    try:
                        bgr = overlay_q.get_nowait()
                        cv2.imshow("Tank Controls — Overlay", bgr)
                    except _tq.Empty:
                        pass
                if cv2.waitKey(16) == 27:  # ESC
                    break
        except KeyboardInterrupt:
            logging.info("Stopped.")
        finally:
            cv2.destroyAllWindows()

        t.join(timeout=2.0)
        if exc_holder:
            logging.error("Fatal error: %s", exc_holder[0])
            sys.exit(1)
    else:
        try:
            asyncio.run(
                _run_pipeline(config, args.dry_run, feedback=emitter)
            )
        except KeyboardInterrupt:
            logging.info("Stopped.")
        except Exception as e:
            logging.error("Fatal error: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the full test suite**

```bash
uv run ruff check . && uv run mypy src/ && uv run pytest
```
Expected: all checks pass, all tests pass (count will have grown from 70 to ~85).

- [ ] **Step 3: Commit**

```bash
git add src/tank_controls/main.py
git commit -m "feat: wire PanicGate, FeedbackEmitter, --log-feedback, --overlay-feedback into pipeline"
```
