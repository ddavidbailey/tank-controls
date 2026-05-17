import sys
from unittest.mock import MagicMock

# Mock webrtcvad at import time to avoid pkg_resources issues.
# Individual tests patch tank_controls.audio.vad.webrtcvad.Vad to set side_effects.
sys.modules["webrtcvad"] = MagicMock()

# Mock pynput at import time to avoid system access requirements.
# Individual tests patch tank_controls.hid.output.Controller to set side_effects.
pynput_mock = MagicMock()
pynput_mock.keyboard.Key = MagicMock()
# Import Key from real module so tests can use pynput.keyboard.Key
try:
    from pynput.keyboard import Key

    pynput_mock.keyboard.Key = Key
except ImportError:
    pass
sys.modules["pynput"] = pynput_mock
sys.modules["pynput.keyboard"] = pynput_mock.keyboard

# Mock sounddevice and faster_whisper at import time to avoid hardware requirements.
sys.modules["sounddevice"] = MagicMock()
sys.modules["faster_whisper"] = MagicMock()
