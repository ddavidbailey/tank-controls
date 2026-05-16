import sys
from unittest.mock import MagicMock

# Mock webrtcvad at import time to avoid pkg_resources issues.
# Individual tests patch tank_controls.audio.vad.webrtcvad.Vad to set side_effects.
sys.modules["webrtcvad"] = MagicMock()
