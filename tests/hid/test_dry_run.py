import logging

import pytest

from tank_controls.hid.dry_run import log_action


def test_log_press_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("fire", "press", "space")
    assert "[DRY-RUN] press: space (fire)" in caplog.text


def test_log_hold_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("throttle_up", "hold", "w")
    assert "[DRY-RUN] hold: w (throttle_up)" in caplog.text


def test_log_mouse_action(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="tank_controls.hid.dry_run"):
        log_action("turret_traverse", "mouse_move", "relative")
    assert "[DRY-RUN] mouse_move: relative (turret_traverse)" in caplog.text
