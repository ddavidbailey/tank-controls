from __future__ import annotations

import logging
import queue as _tq
import time
from typing import TYPE_CHECKING, Any

from pynput.keyboard import Controller  # type: ignore[import-untyped]

from tank_controls.hid._keys import parse_binding

if TYPE_CHECKING:
    from tank_controls.hid.panic import PanicGate

logger = logging.getLogger(__name__)


class KeyPresser:
    def __init__(
        self,
        cooldown_ms: int = 200,
        dispatch_q: "_tq.Queue[Any] | None" = None,
    ) -> None:
        self._controller = Controller()
        self._cooldown_ms = cooldown_ms
        self._last_fired: dict[str, float] = {}
        self._dispatch_q = dispatch_q

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

        modifiers, key = parse_binding(binding)

        def do_press() -> None:
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

        if self._dispatch_q is not None:
            try:
                self._dispatch_q.put_nowait(do_press)
            except _tq.Full:
                pass
        else:
            do_press()
        return True
