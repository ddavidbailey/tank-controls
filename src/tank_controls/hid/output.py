import logging
import time

from pynput.keyboard import Controller, Key  # type: ignore[import-untyped]

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


class KeyPresser:
    def __init__(self, cooldown_ms: int = 200) -> None:
        self._controller = Controller()
        self._cooldown_ms = cooldown_ms
        self._last_fired: dict[str, float] = {}

    def press(self, action_name: str, binding: str) -> bool:
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

    def _parse_binding(self, binding: str) -> tuple[list[Key], Key | str]:
        parts = binding.split("+")
        modifiers = [_MODIFIER_MAP[p] for p in parts[:-1] if p in _MODIFIER_MAP]
        key_str = parts[-1]
        key: Key | str = _SPECIAL_KEY_MAP.get(key_str, key_str)
        return modifiers, key
