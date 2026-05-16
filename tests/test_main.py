import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from tank_controls.main import main


def test_main_logs_profile_and_commands(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')

    def close_coro(coro: object, **_: object) -> None:
        import inspect
        if inspect.iscoroutine(coro):
            coro.close()

    with patch("sys.argv", ["tank-controls", "--config", str(f), "--dry-run"]), \
         patch("tank_controls.main.asyncio.run", side_effect=close_coro), \
         caplog.at_level(logging.INFO):
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
