# Phase C: Vision Pipeline Design

**Date:** 2026-05-17
**Scope:** Two-hand camera tracking — frame capture, MediaPipe landmark detection, quadrant-based drive control, distance-scaled turret mouse control

## Goal

Map left-hand position to tank drive inputs (W/A/S/D) and right-hand position to turret mouse movement, running concurrently with the Phase B voice pipeline in the same asyncio event loop.

---

## Pipeline

Two new coroutines join the existing `asyncio.gather()` alongside the voice pipeline:

```
[Existing - Phase B]
AudioCapture → VAD → STT → intent_queue → VoiceHID

[New - Phase C]
Camera → MediaPipe → gesture_queue → GestureHID
```

Camera frames are captured in a background thread and forwarded via `loop.call_soon_threadsafe`. MediaPipe runs in a `ThreadPoolExecutor`. The gesture coroutine computes drive key sets and turret mouse deltas each frame and pushes a `GestureState` into `gesture_queue`. The `GestureHID` coroutine reads that state and holds/releases keys or moves the mouse accordingly.

---

## Hand assignment

MediaPipe Hand Landmarker (`max_hands=2`) labels each detected hand as `"Left"` or `"Right"`. Left hand → drive quadrant logic. Right hand → turret mouse logic. Each hand is tracked independently — if one leaves the frame, its keys are released immediately and the other continues unaffected.

Only **landmark 0 (wrist)** is used as the position reference. Coordinates are normalised to `[0.0, 1.0]` relative to the full frame.

---

## Neutral reference points

No calibration required. Reference centres are fixed:

| Hand | Frame region | Neutral centre |
|---|---|---|
| Left | Left half of frame | `(0.25, 0.5)` |
| Right | Right half of frame | `(0.75, 0.5)` |

---

## Left hand — drive quadrant (`vision/gesture.py`)

The wrist position is compared against `(0.25, 0.5)`. A configurable `quadrant_threshold` (fraction of full frame) defines a deadzone around centre. Outside the deadzone, X and Y offsets are checked independently:

| X offset | Y offset | Actions held |
|---|---|---|
| within threshold | within threshold | none (deadzone) |
| right | up | `throttle_up` + `turn_right` |
| centre | up | `throttle_up` |
| left | up | `throttle_up` + `turn_left` |
| right | centre | `turn_right` |
| left | centre | `turn_left` |
| right | down | `throttle_down` + `turn_right` |
| centre | down | `throttle_down` |
| left | down | `throttle_down` + `turn_left` |

Output is a `set[str]` of action names (e.g. `{"throttle_up", "turn_right"}`). These map to the user's `[hold]` config bindings. The gesture HID compares against the previous frame's set — newly added actions are pressed, dropped actions are released.

---

## Right hand — turret mouse (`vision/gesture.py`)

The wrist offset from `(0.75, 0.5)` is normalised to `[-1.0, 1.0]` and multiplied by `max_mouse_speed` to produce a pixel delta per frame:

```
dx = (wrist_x - 0.75) / 0.5 * max_mouse_speed
dy = (wrist_y - 0.5)  / 0.5 * max_mouse_speed   # positive Y = downward on screen
```

The same `quadrant_threshold` deadzone produces `(0, 0)` delta when the hand is near centre. Diagonal positions produce both X and Y movement naturally. Mouse delta is emitted every frame the right wrist is detected outside the deadzone.

---

## Config additions

New `[vision]` section in the TOML. All fields optional with defaults shown.

```toml
[vision]
camera_index = 0          # which webcam to use (default 0)
frame_width = 640
frame_height = 480
fps = 30
quadrant_threshold = 0.1  # deadzone radius as fraction of frame width/height
max_mouse_speed = 15      # max pixels per frame for turret mouse movement
```

A `VisionConfig` dataclass is added to `src/tank_controls/config/loader.py` and parsed from `[vision]` alongside the existing `VoiceConfig`.

---

## GestureState dataclass

```python
@dataclass
class HandState:
    left_wrist: tuple[float, float] | None   # normalised (x, y), None if not detected
    right_wrist: tuple[float, float] | None
```

The gesture coroutine converts `HandState` into a `GestureState`:

```python
@dataclass
class GestureState:
    hold_actions: set[str]          # action names to hold this frame (drive)
    mouse_delta: tuple[int, int]    # (dx, dy) for turret this frame
```

---

## HID output (`vision/hid.py`)

Maintains `held_actions: set[str]` between frames. Sustained holds require `keyboard.press()` / `keyboard.release()` directly — not `KeyPresser`, which does press-and-release (a tap). The binding parser from `hid/output.py` (`_parse_binding`) is reused to convert `[hold]` config strings into pynput keys.

- Actions in new set but not old → `keyboard.press(key)` for each key in the binding
- Actions in old set but not new → `keyboard.release(key)` for each key in the binding
- Mouse delta applied each frame via `pynput.mouse.Controller().move(dx, dy)`

On shutdown or when both hands leave frame, all currently held keys are released before exit.

---

## Error handling

| Failure | Behaviour |
|---|---|
| Camera not found / permission denied | Log error at startup, exit code 1 |
| MediaPipe model not downloaded | Propagates at startup, logged, exit code 1 |
| Hand leaves frame | Release all keys for that hand immediately next frame |
| Both hands leave frame | All gesture keys released, mouse delta becomes (0, 0) |
| Frame queue full | Drop incoming frame — fresh frames are always preferred |

---

## Testing

Hardware-dependent stages (camera, MediaPipe) are not unit tested. Logic is:

| File | What is tested |
|---|---|
| `tests/vision/test_gesture.py` | All 9 drive quadrant zones, deadzone boundary, mouse delta scaling, diagonal mouse deltas, hand-absent produces empty hold set and zero delta |

---

## Files created or modified

| File | Action |
|---|---|
| `src/tank_controls/vision/capture.py` | Create — OpenCV frame capture thread |
| `src/tank_controls/vision/landmarks.py` | Create — MediaPipe Hand Landmarker wrapper |
| `src/tank_controls/vision/gesture.py` | Create — HandState → GestureState logic |
| `src/tank_controls/vision/hid.py` | Create — key hold/release + mouse movement |
| `src/tank_controls/config/loader.py` | Modify — add `VisionConfig` dataclass, parse `[vision]` section |
| `src/tank_controls/main.py` | Modify — add vision coroutines to `asyncio.gather()` |
| `tests/vision/__init__.py` | Create |
| `tests/vision/test_gesture.py` | Create |
