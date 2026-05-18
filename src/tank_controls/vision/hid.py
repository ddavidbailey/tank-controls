from __future__ import annotations

import logging
import queue as _tq
from typing import TYPE_CHECKING, Any

from pynput.keyboard import Controller as KeyboardController  # type: ignore[import-untyped]
from pynput.mouse import Controller as MouseController  # type: ignore[import-untyped]

from tank_controls.hid._keys import parse_binding
from tank_controls.vision.gesture import GestureState

if TYPE_CHECKING:
    from tank_controls.hid.feedback import FeedbackEmitter

logger = logging.getLogger(__name__)


class GestureHID:
    def __init__(
        self,
        hold_bindings: dict[str, str],
        feedback: "FeedbackEmitter | None" = None,
        dispatch_q: "_tq.Queue[Any] | None" = None,
    ) -> None:
        self._keyboard = KeyboardController()
        self._mouse = MouseController()
        self._hold_bindings = hold_bindings
        self._held: set[str] = set()
        self._turret_active: bool = False
        self._feedback = feedback
        self._dispatch_q = dispatch_q

    def _run(self, fn: Any) -> None:
        if self._dispatch_q is not None:
            try:
                self._dispatch_q.put_nowait(fn)
            except _tq.Full:
                pass
        else:
            fn()

    def apply(self, state: GestureState) -> None:
        prev_held = set(self._held)

        for action in self._held - state.hold_actions:
            self._release(action)
        for action in state.hold_actions - self._held:
            self._press(action)
        self._held = set(state.hold_actions)

        dx, dy = state.mouse_delta
        if dx != 0 or dy != 0:
            def do_move(x: int = dx, y: int = dy) -> None:
                try:
                    self._mouse.move(x, y)
                except Exception:
                    logger.warning("Mouse move failed — check Accessibility in System Settings.")
            self._run(do_move)

        turret_now = state.mouse_delta != (0, 0)
        hold_changed = self._held != prev_held
        turret_changed = turret_now != self._turret_active
        self._turret_active = turret_now
        if self._feedback is not None and (hold_changed or turret_changed):
            self._feedback.emit_gesture(state, turret_active=turret_now)

    def release_all(self) -> None:
        for action in list(self._held):
            self._release(action)
        self._held = set()

    def _press(self, action: str) -> None:
        binding = self._hold_bindings.get(action, "")
        if not binding:
            return
        modifiers, key = parse_binding(binding)

        def do_press() -> None:
            try:
                for mod in modifiers:
                    self._keyboard.press(mod)
                self._keyboard.press(key)
            except Exception:
                logger.warning(
                    "Key press failed for '%s' — check Accessibility in System Settings.", binding
                )

        self._run(do_press)

    def _release(self, action: str) -> None:
        binding = self._hold_bindings.get(action, "")
        if not binding:
            return
        modifiers, key = parse_binding(binding)

        def do_release() -> None:
            try:
                self._keyboard.release(key)
                for mod in reversed(modifiers):
                    self._keyboard.release(mod)
            except Exception:
                logger.warning("Key release failed for '%s'.", binding)

        self._run(do_release)
