# Phase D: Fusion — Design Spec

## Goal

Add a global panic-disable hotkey that pauses all HID output (voice and gesture) and releases held keys, plus configurable state feedback via terminal logs and/or a status HUD overlay.

## Architecture

Three new units slot into the existing pipeline without restructuring it:

1. **`PanicGate`** (`hid/panic.py`) — owns the paused state and the global hotkey listener
2. **`FeedbackEmitter`** (`hid/feedback.py`) — emits state changes to the terminal and/or overlay queue
3. **Status HUD** — rendered in the existing main-thread display loop alongside `--debug`

The voice and gesture HID classes each gain an optional `gate` parameter. No other pipeline stages change.

## Components

### PanicGate (`src/tank_controls/hid/panic.py`)

- Owns a `threading.Event` (`_paused`). Set = paused, clear = live.
- Starts a `pynput.keyboard.GlobalHotKeys({'<shift>+`': _on_toggle})` listener in a daemon thread on `start()`.
- `_on_toggle()`: if paused → clear flag; if live → set flag, call the injected `release_fn()` immediately (bound to `GestureHID.release_all`).
- Calls the injected `on_toggle(paused: bool)` callback after every state change (used by `FeedbackEmitter`).
- `is_paused() → bool` — checked by HID classes before acting.
- `stop()` — stops the listener thread; called in the pipeline `finally` block.

### FeedbackEmitter (`src/tank_controls/hid/feedback.py`)

Constructed with `log: bool` and `display_queue: queue.Queue | None`.

- `emit_toggle(paused: bool)` — called by `PanicGate`. Logs `INFO [PAUSED]` or `INFO [RESUMED]` when `log=True`. Pushes `{"paused": paused}` to `display_queue` when set.
- `emit_gesture(state: GestureState)` — called from `GestureHID.apply()` only when `hold_actions` changes (not every frame). Logs active drive actions when `log=True`. Pushes `{"state": state}` to `display_queue` when set.

When both `log=False` and `display_queue=None`, all methods are no-ops.

### HID integration

**`KeyPresser.press()`** (`hid/output.py`): accepts `gate: PanicGate | None = None`. Returns immediately if `gate.is_paused()`.

**`GestureHID`** (`vision/hid.py`): accepts `gate: PanicGate | None = None` and `feedback: FeedbackEmitter | None = None` in `__init__`. `apply()` skips all output (calls `release_all()`) if `gate.is_paused()`. Calls `feedback.emit_gesture(state)` when `hold_actions` changes.

Passing `gate=None` (the default) preserves existing behaviour exactly — no tests need updating.

### Status HUD overlay

A small 400×100 black cv2 window rendered in the main thread. Active when `--overlay-feedback` is passed. Three text lines:

```
● LIVE          (green)  /  ● PAUSED       (red)
Drive: W + D             (green, or blank)
Turret: dx=+5 dy=-2      (orange, or blank)
```

The main-thread display loop handles both the camera debug window (if `--debug`) and the status window (if `--overlay-feedback`) from their respective thread queues in the same `cv2.waitKey(16)` loop. The status window is created with `cv2.namedWindow` before the loop starts.

## CLI

```
--log-feedback      Emit INFO logs on pause/resume and drive action changes
--overlay-feedback  Show status HUD window (independent of --debug)
```

Both flags are optional and combinable. Neither implies the other. `--overlay-feedback` without `--debug` shows only the HUD, not the camera feed.

## Data Flow

```
GlobalHotKeys thread
  └─ PanicGate._on_toggle()
       ├─ GestureHID.release_all()          # immediate key release
       └─ FeedbackEmitter.emit_toggle()
            ├─ logging.info(...)            # if --log-feedback
            └─ status_queue.put(...)        # if --overlay-feedback

_gesture_hid_stage (asyncio)
  └─ GestureHID.apply(state)
       ├─ returns early if gate.is_paused()
       └─ FeedbackEmitter.emit_gesture(state)  # on hold_actions change only

_hid_stage (asyncio)
  └─ KeyPresser.press(action, binding, gate)
       └─ returns early if paused

main() display loop (main thread)
  ├─ debug_queue  → cv2.imshow camera window    # if --debug
  └─ status_queue → cv2.imshow HUD window       # if --overlay-feedback
```

## File Changes

| File | Change |
|------|--------|
| `src/tank_controls/hid/panic.py` | New — `PanicGate` |
| `src/tank_controls/hid/feedback.py` | New — `FeedbackEmitter` |
| `src/tank_controls/hid/output.py` | Add optional `gate` param to `KeyPresser.press()` |
| `src/tank_controls/vision/hid.py` | Add optional `gate` param to `GestureHID.__init__` and `apply()` |
| `src/tank_controls/main.py` | New flags, wire gate + emitter, extend display loop |
| `tests/hid/test_panic.py` | New — PanicGate unit tests |
| `tests/hid/test_feedback.py` | New — FeedbackEmitter unit tests |

## Out of Scope

- Gesture debounce (deferred to a later phase)
- Audio feedback (beeps/tones)
- Per-action feedback (only drive action changes and pause/resume events are reported)
