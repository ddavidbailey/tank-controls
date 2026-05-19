from unittest.mock import MagicMock, call, patch

from pynput.keyboard import Key
from pynput.mouse import Button

from tank_controls.hid.output import KeyPresser


# Helpers that force the pynput fallback path (disable Quartz bypass) so
# tests can assert on Controller.press/release without platform dependency.
def _no_quartz():
    return patch("tank_controls.hid.output._KB_QUARTZ", False)


def _quartz_tap():
    return patch("tank_controls.hid.output._quartz_key_tap")


def test_quartz_used_for_simple_key():
    with (
        patch("tank_controls.hid.output.Controller"),
        _quartz_tap() as mock_tap,
    ):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("one", "1")
        assert result is True
        mock_tap.assert_called_once()
        args = mock_tap.call_args[0]
        assert args[0] == 18  # kVK_ANSI_1
        assert args[1] == 0   # no down flags for a plain key


def test_quartz_ctrl_combo_passes_flag():
    with (
        patch("tank_controls.hid.output.Controller"),
        _quartz_tap() as mock_tap,
    ):
        presser = KeyPresser(cooldown_ms=0)
        presser.press("range_finder", "ctrl+r")
        mock_tap.assert_called_once()
        import Quartz
        args = mock_tap.call_args[0]
        assert args[0] == 15  # kVK_ANSI_R
        assert args[1] & Quartz.kCGEventFlagMaskControl


def test_quartz_shift_standalone_sets_own_flag():
    with (
        patch("tank_controls.hid.output.Controller"),
        _quartz_tap() as mock_tap,
    ):
        presser = KeyPresser(cooldown_ms=0)
        presser.press("scope", "shift")
        mock_tap.assert_called_once()
        import Quartz

        args = mock_tap.call_args[0]
        assert args[0] == 56  # kVK_Shift (left)
        assert args[1] & Quartz.kCGEventFlagMaskShift
        assert args[2] == 0


def test_quartz_cmd_standalone_sets_own_flag():
    with (
        patch("tank_controls.hid.output.Controller"),
        _quartz_tap() as mock_tap,
    ):
        presser = KeyPresser(cooldown_ms=0)
        presser.press("range_finder", "cmd")
        mock_tap.assert_called_once()
        import Quartz
        args = mock_tap.call_args[0]
        # VK for cmd is 0x37 = 55
        assert args[0] == 0x37
        # down_flags must include kCGEventFlagMaskCommand
        assert args[1] & Quartz.kCGEventFlagMaskCommand
        # up_flags must be 0 (modifier cleared on release)
        assert args[2] == 0


def test_pynput_fallback_single_key():
    with (
        _no_quartz(),
        patch("tank_controls.hid.output.Controller") as MockController,
    ):
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space")
        assert result is True
        controller.press.assert_any_call(Key.space)
        controller.release.assert_any_call(Key.space)


def test_pynput_fallback_combo_presses_modifier_before_key():
    with (
        _no_quartz(),
        patch("tank_controls.hid.output.Controller") as MockController,
    ):
        controller = MockController.return_value
        presser = KeyPresser(cooldown_ms=0)
        presser.press("range_finder", "ctrl+r")
        assert controller.press.call_count == 2
        assert controller.press.call_args_list[0] == call(Key.ctrl)
        assert controller.release.call_count == 2
        assert controller.release.call_args_list[1] == call(Key.ctrl)


def test_cooldown_blocks_immediate_repeat():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
        _quartz_tap(),
    ):
        mock_time.monotonic.side_effect = [0.0, 0.1]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")
        result = presser.press("fire", "space")
        assert result is False


def test_cooldown_allows_press_after_elapsed():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
        _quartz_tap(),
    ):
        mock_time.monotonic.side_effect = [0.0, 0.3]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")
        result = presser.press("fire", "space")
        assert result is True


def test_cooldown_is_independent_per_action():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.time") as mock_time,
        _quartz_tap(),
    ):
        mock_time.monotonic.side_effect = [0.0, 0.05]
        presser = KeyPresser(cooldown_ms=200)
        presser.press("fire", "space")
        result = presser.press("range_finder", "ctrl+r")
        assert result is True


def _quartz_click():
    return patch("tank_controls.hid.output._quartz_mouse_click")


def test_mouse1_clicks_left_button():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.MouseController"),
        _quartz_click() as mock_click,
    ):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "mouse1")
        assert result is True
        mock_click.assert_called_once_with(Button.left)


def test_mouse2_clicks_right_button():
    with (
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.MouseController"),
        _quartz_click() as mock_click,
    ):
        presser = KeyPresser(cooldown_ms=0)
        presser.press("alt_fire", "mouse2")
        mock_click.assert_called_once_with(Button.right)


def test_mouse_binding_does_not_touch_keyboard():
    with (
        patch("tank_controls.hid.output.Controller") as MockKbd,
        patch("tank_controls.hid.output.MouseController"),
        _quartz_click(),
    ):
        kbd = MockKbd.return_value
        presser = KeyPresser(cooldown_ms=0)
        presser.press("fire", "mouse1")
        kbd.press.assert_not_called()


def test_pynput_fallback_mouse_click():
    with (
        _no_quartz(),
        patch("tank_controls.hid.output.Controller"),
        patch("tank_controls.hid.output.MouseController") as MockMouse,
    ):
        mouse = MockMouse.return_value
        presser = KeyPresser(cooldown_ms=0)
        presser.press("fire", "mouse1")
        mouse.click.assert_called_once_with(Button.left)


def test_press_blocked_when_gate_paused() -> None:
    gate = MagicMock()
    gate.is_paused.return_value = True
    with patch("tank_controls.hid.output.Controller"):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space", gate=gate)
    assert result is False


def test_press_allowed_when_gate_live() -> None:
    gate = MagicMock()
    gate.is_paused.return_value = False
    with (
        patch("tank_controls.hid.output.Controller"),
        _quartz_tap(),
    ):
        presser = KeyPresser(cooldown_ms=0)
        result = presser.press("fire", "space", gate=gate)
    assert result is True
