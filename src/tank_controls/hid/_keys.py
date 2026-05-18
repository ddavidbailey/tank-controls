import sys

from pynput.keyboard import Key, KeyCode  # type: ignore[import-untyped]

MODIFIER_MAP: dict[str, Key] = {
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
}

SPECIAL_KEY_MAP: dict[str, Key] = {
    "space": Key.space,
    "enter": Key.enter,
    "tab": Key.tab,
    "escape": Key.esc,
    **{f"f{i}": getattr(Key, f"f{i}") for i in range(1, 13)},
}

# macOS ANSI virtual key codes — used instead of character strings to avoid
# TSMGetInputSourceProperty calls that assert the main dispatch queue and crash
# when called from a background thread.
_MAC_ANSI_VK: dict[str, int] = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15,
    "y": 16, "t": 17, "1": 18, "2": 19, "3": 20, "4": 21, "6": 22,
    "5": 23, "9": 25, "7": 26, "8": 28, "0": 29, "o": 31, "u": 32,
    "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
}


def resolve_key(key_str: str) -> "Key | KeyCode | str":
    if key_str in SPECIAL_KEY_MAP:
        return SPECIAL_KEY_MAP[key_str]
    if sys.platform == "darwin" and key_str in _MAC_ANSI_VK:
        return KeyCode(vk=_MAC_ANSI_VK[key_str])
    return key_str


def parse_binding(binding: str) -> "tuple[list[Key], Key | KeyCode | str]":
    parts = binding.split("+")
    modifiers = [MODIFIER_MAP[p] for p in parts[:-1] if p in MODIFIER_MAP]
    return modifiers, resolve_key(parts[-1])
