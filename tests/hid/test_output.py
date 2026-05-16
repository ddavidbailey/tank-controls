from unittest.mock import call, patch

from pynput.keyboard import Key

from tank_controls.hid.output import KeyPresser


def test_single_key_press_calls_controller():
    with patch("tank_controls.hid.output.Controller") as MockController:
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space")
        assert result is True
        controller.press.assert_any_call(Key.space)
        controller.release.assert_any_call(Key.space)


def test_combo_presses_modifier_before_key_releases_in_reverse():
    with patch("tank_controls.hid.output.Controller") as MockController:
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        presser.press("range_finder", "ctrl+r")
        assert controller.press.call_args_list == [call(Key.ctrl), call("r")]
        assert controller.release.call_args_list == [call("r"), call(Key.ctrl)]


def test_cooldown_blocks_immediate_repeat():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = [0.0, 0.1]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")  # first press at t=0.0
        result = presser.press("fire", "space")  # second at t=0.1 → 100ms < 200ms
        assert result is False


def test_cooldown_allows_press_after_elapsed():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = [0.0, 0.3]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")  # first press at t=0.0
        result = presser.press("fire", "space")  # second at t=0.3 → 300ms > 200ms
        assert result is True


def test_cooldown_is_independent_per_action():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
    ):
        mock_time.monotonic.side_effect = [0.0, 0.05]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")
        result = presser.press("range_finder", "ctrl+r")  # different action, no cooldown
        assert result is True
