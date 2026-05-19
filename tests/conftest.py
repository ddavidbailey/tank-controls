import sys
from unittest.mock import MagicMock

# Mock pynput at import time to avoid system access requirements.
# Individual tests patch tank_controls.hid.output.Controller to set side_effects.
pynput_mock = MagicMock()
pynput_mock.keyboard.Key = MagicMock()
pynput_mock.keyboard.KeyCode = MagicMock()
# Preserve real Key and KeyCode so tests can use them for assertions and VK lookups
try:
    from pynput.keyboard import Key, KeyCode

    pynput_mock.keyboard.Key = Key
    pynput_mock.keyboard.KeyCode = KeyCode
except ImportError:
    pass
sys.modules["pynput"] = pynput_mock
sys.modules["pynput.keyboard"] = pynput_mock.keyboard
sys.modules["pynput.mouse"] = pynput_mock.mouse

# Mock sounddevice and faster_whisper at import time to avoid hardware requirements.
sys.modules["sounddevice"] = MagicMock()
sys.modules["mlx_whisper"] = MagicMock()

# Mock cv2 and mediapipe (including Tasks API submodules) to avoid hardware requirements.
sys.modules["cv2"] = MagicMock()
mediapipe_mock = MagicMock()
sys.modules["mediapipe"] = mediapipe_mock
sys.modules["mediapipe.tasks"] = mediapipe_mock.tasks
sys.modules["mediapipe.tasks.python"] = mediapipe_mock.tasks.python
sys.modules["mediapipe.tasks.python.vision"] = mediapipe_mock.tasks.python.vision
