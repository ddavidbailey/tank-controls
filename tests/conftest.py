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
# The async pipeline (asyncio.run) is also stubbed so tests return immediately.
sys.modules["sounddevice"] = MagicMock()
sys.modules["faster_whisper"] = MagicMock()

import asyncio  # noqa: E402
from unittest.mock import patch  # noqa: E402

_real_asyncio_run = asyncio.run


def _noop_asyncio_run(coro: object, **kwargs: object) -> None:
    """No-op replacement for asyncio.run used during tests.

    Prevents the pipeline coroutine from blocking the test suite while still
    allowing all pre-pipeline logic (config loading, startup logging) to execute.
    """
    import inspect

    if inspect.iscoroutine(coro):
        coro.close()  # prevent RuntimeWarning about unawaited coroutine


# Patch asyncio.run globally for the test session so pipeline tests return fast.
patch("asyncio.run", side_effect=_noop_asyncio_run).start()
