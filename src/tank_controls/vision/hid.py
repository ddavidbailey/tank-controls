from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
        modifiers, key = parse_binding(binding)
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
        modifiers, key = parse_binding(binding)
        try:
            self._keyboard.release(key)
            for mod in reversed(modifiers):
                self._keyboard.release(mod)
        except Exception:
            logger.warning("Key release failed for '%s'.", binding)
