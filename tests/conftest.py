import sys
from unittest.mock import MagicMock

# Mock webrtcvad before any test imports it
sys.modules["webrtcvad"] = MagicMock()
