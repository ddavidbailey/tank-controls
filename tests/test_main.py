import inspect
import logging
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from tank_controls.main import main


def test_main_logs_profile_and_commands(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')

    def close_coro(coro: object, **_: object) -> None:
        if inspect.iscoroutine(coro):
            coro.close()

    with (
        patch("sys.argv", ["tank-controls", "--config", str(f), "--dry-run", "--mic", "0"]),
        patch("tank_controls.main.asyncio.run", side_effect=close_coro),
        caplog.at_level(logging.INFO),
    ):
        main()
    assert "Loaded profile: test" in caplog.text
    assert "Listening for: fire" in caplog.text


def test_main_exits_on_missing_config(tmp_path: Path) -> None:
    with patch("sys.argv", ["tank-controls", "--config", str(tmp_path / "missing.toml")]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_main_exits_on_config_error(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[press]\nfire = ""\n')
    with patch("sys.argv", ["tank-controls", "--config", str(f)]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 1


def test_main_log_feedback_flag_exits_cleanly(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')

    def close_coro(coro: object, **_: object) -> None:
        if inspect.iscoroutine(coro):
            coro.close()

    with (
        patch("sys.argv", ["tank-controls", "--config", str(f), "--dry-run", "--log-feedback", "--mic", "0"]),
        patch("tank_controls.main.asyncio.run", side_effect=close_coro),
    ):
        main()  # should not raise


def test_main_overlay_feedback_flag_uses_display_thread(tmp_path: Path) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')

    thread_started = []

    original_thread = threading.Thread

    def patched_thread(**kwargs: object) -> object:
        t = original_thread(**kwargs)  # type: ignore[arg-type]
        thread_started.append(True)
        return t

    from unittest.mock import MagicMock

    def close_coro(coro: object, **_: object) -> None:
        if inspect.iscoroutine(coro):
            coro.close()

    mock_cv2 = MagicMock()
    mock_cv2.waitKey.return_value = 27  # ESC immediately exits loop
    mock_cv2.WINDOW_AUTOSIZE = 0

    mock_audio = MagicMock()
    mock_audio.start.return_value = MagicMock()  # mock stream

    with (
        patch("sys.argv", ["tank-controls", "--config", str(f), "--dry-run", "--overlay-feedback", "--mic", "0"]),
        patch("tank_controls.main.threading.Thread", side_effect=patched_thread),
        patch("tank_controls.main.asyncio.run", side_effect=close_coro),
        patch("tank_controls.main.AudioCapture", return_value=mock_audio),
        patch.dict("sys.modules", {"cv2": mock_cv2}),
    ):
        main()

    assert thread_started, "display thread should have been started for --overlay-feedback"
