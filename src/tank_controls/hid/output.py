from __future__ import annotations

import logging
import queue as _tq
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

from pynput.keyboard import Controller, Key, KeyCode  # type: ignore[import-untyped]
from pynput.mouse import Button  # type: ignore[import-untyped]
from pynput.mouse import Controller as MouseController  # type: ignore[import-untyped]

from tank_controls.hid._keys import parse_binding

# On macOS, CGEvent-based keyboard injection must set flags explicitly.
# pynput's Controller builds flags from its own internal modifier-state tracking,
# which can be stale or wrong when the game holds modifiers outside pynput's
# awareness.  Posting the event directly via Quartz with clean flags avoids this.
try:
    if sys.platform == "darwin":
        import Quartz as _Quartz  # type: ignore[import-untyped]
        _KB_QUARTZ = True
        _MOD_CGF: dict[Key, int] = {
            Key.ctrl: _Quartz.kCGEventFlagMaskControl,
            Key.alt: _Quartz.kCGEventFlagMaskAlternate,
            Key.shift: _Quartz.kCGEventFlagMaskShift,
            Key.cmd: _Quartz.kCGEventFlagMaskCommand,
        }
    else:
        _KB_QUARTZ = False
except ImportError:
    _KB_QUARTZ = False

_MOUSE_BUTTONS: dict[str, Button] = {
    "mouse1": Button.left,
    "mouse2": Button.right,
    "mouse3": Button.middle,
}

if TYPE_CHECKING:
    from tank_controls.hid.panic import PanicGate

logger = logging.getLogger(__name__)

# Games poll input state rather than processing events; a zero-duration tap is
# invisible to them.  Hold key/button down for this long before releasing.
_HOLD_S = 0.050  # 50 ms


def _key_vk(key: object) -> "int | None":
    # Key enum member: its .value is a KeyCode carrying .vk
    val = getattr(key, "value", None)
    if val is not None:
        vk = getattr(val, "vk", None)
        if isinstance(vk, int):
            return vk
    # Bare KeyCode
    vk = getattr(key, "vk", None)
    return vk if isinstance(vk, int) else None


def _quartz_key_tap(vk: int, down_flags: int, up_flags: "int | None" = None) -> None:
    if up_flags is None:
        up_flags = down_flags
    down = _Quartz.CGEventCreateKeyboardEvent(None, vk, True)
    _Quartz.CGEventSetFlags(down, down_flags)
    _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, down)

    uf = up_flags

    def _release() -> None:
        up = _Quartz.CGEventCreateKeyboardEvent(None, vk, False)
        _Quartz.CGEventSetFlags(up, uf)
        _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, up)

    threading.Timer(_HOLD_S, _release).start()


def _quartz_mouse_click(button: Button) -> None:
    """Post a mouse button click directly via Quartz, bypassing pynput."""
    if button == Button.left:
        d, u, b = _Quartz.kCGEventLeftMouseDown, _Quartz.kCGEventLeftMouseUp, 0
    elif button == Button.right:
        d, u, b = _Quartz.kCGEventRightMouseDown, _Quartz.kCGEventRightMouseUp, 1
    else:
        d, u, b = _Quartz.kCGEventOtherMouseDown, _Quartz.kCGEventOtherMouseUp, 2
    pos = _Quartz.CGEventGetLocation(_Quartz.CGEventCreate(None))
    down = _Quartz.CGEventCreateMouseEvent(None, d, pos, b)
    _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, down)

    def _release() -> None:
        up = _Quartz.CGEventCreateMouseEvent(None, u, pos, b)
        _Quartz.CGEventPost(_Quartz.kCGHIDEventTap, up)

    threading.Timer(_HOLD_S, _release).start()


class KeyPresser:
    def __init__(
        self,
        cooldown_ms: int = 200,
        dispatch_q: "_tq.Queue[Any] | None" = None,
    ) -> None:
        self._controller = Controller()
        self._mouse = MouseController()
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

        if binding in _MOUSE_BUTTONS:
            button = _MOUSE_BUTTONS[binding]

            if _KB_QUARTZ:
                def do_press(btn: Button = button) -> None:
                    try:
                        _quartz_mouse_click(btn)
                    except Exception:
                        logger.warning(
                            "Failed to click '%s'. "
                            "Grant Accessibility access in System Settings → Privacy & Security.",
                            binding,
                        )
            else:
                def do_press() -> None:  # type: ignore[misc]
                    try:
                        self._mouse.click(button)
                    except Exception:
                        logger.warning(
                            "Failed to click '%s'. "
                            "Grant Accessibility access in System Settings → Privacy & Security.",
                            binding,
                        )
        else:
            modifiers, key = parse_binding(binding)

            if _KB_QUARTZ:
                flags = 0
                for mod in modifiers:
                    flags |= _MOD_CGF.get(mod, 0)
                vk = _key_vk(key)

                if vk is not None:
                    # If the key itself is a modifier (e.g. cmd pressed alone),
                    # set its flag on keydown so the OS sees the modifier active,
                    # then clear it on keyup.
                    own_flag = _MOD_CGF.get(key, 0)  # type: ignore[arg-type]
                    down_f = flags | own_flag
                    up_f = flags

                    def do_press(vk_: int = vk, df: int = down_f, uf: int = up_f) -> None:  # type: ignore[misc]
                        try:
                            _quartz_key_tap(vk_, df, uf)
                        except Exception:
                            logger.warning(
                                "Failed to press '%s'. "
                                "Grant Accessibility access in System Settings → Privacy & Security.",
                                binding,
                            )
                else:
                    def do_press() -> None:  # type: ignore[misc]
                        logger.warning("No VK code for '%s' — skipping", binding)
            else:
                def do_press() -> None:  # type: ignore[misc]
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
