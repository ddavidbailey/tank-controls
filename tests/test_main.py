import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from tank_controls.main import main


def test_main_logs_actions(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    f = tmp_path / "config.toml"
    f.write_text('[profile]\nname = "test"\n\n[press]\nfire = "space"\n')
    with patch("sys.argv", ["tank-controls", "--config", str(f)]):
        with caplog.at_level(logging.INFO):
            main()
    assert "[DRY-RUN] press: space (fire)" in caplog.text


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
