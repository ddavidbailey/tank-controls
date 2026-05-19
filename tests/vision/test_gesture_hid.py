from unittest.mock import ANY, patch

from tank_controls.vision.gesture import GestureState
from tank_controls.vision.hid import GestureHID


def test_new_action_presses_key() -> None:
    with (
        patch("tank_controls.vision.hid.KeyboardController") as MockKbd,
        patch("tank_controls.vision.hid.MouseController"),
    ):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        kbd.press.assert_called_once()  # key was pressed (exact key resolved by _keys.py)


def test_dropped_action_releases_key() -> None:
    with (
        patch("tank_controls.vision.hid.KeyboardController") as MockKbd,
        patch("tank_controls.vision.hid.MouseController"),
    ):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(0, 0)))
        kbd.release.assert_called_once()  # key was released


def test_mouse_delta_applied() -> None:
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
        patch("tank_controls.vision.hid._post_mouse_move") as mock_move,
    ):
        hid = GestureHID(hold_bindings={})
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(5, -3)))
        mock_move.assert_called_once_with(ANY, 5, -3)


def test_zero_mouse_delta_not_applied() -> None:
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
        patch("tank_controls.vision.hid._post_mouse_move") as mock_move,
    ):
        hid = GestureHID(hold_bindings={})
        hid.apply(GestureState(hold_actions=set(), mouse_delta=(0, 0)))
        mock_move.assert_not_called()


def test_release_all_releases_held_keys() -> None:
    with (
        patch("tank_controls.vision.hid.KeyboardController") as MockKbd,
        patch("tank_controls.vision.hid.MouseController"),
    ):
        kbd = MockKbd.return_value
        hid = GestureHID(hold_bindings={"throttle_up": "w"})
        hid.apply(GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0)))
        hid.release_all()
        kbd.release.assert_called()  # key was released by release_all


def test_feedback_emitted_on_hold_actions_change() -> None:
    from unittest.mock import MagicMock

    feedback = MagicMock()
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
    ):
        hid = GestureHID(hold_bindings={"throttle_up": "w"}, feedback=feedback)
        state = GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0))
        hid.apply(state)
    feedback.emit_gesture.assert_called_once_with(state, turret_active=False)


def test_feedback_not_emitted_when_actions_unchanged() -> None:
    from unittest.mock import MagicMock

    feedback = MagicMock()
    with (
        patch("tank_controls.vision.hid.KeyboardController"),
        patch("tank_controls.vision.hid.MouseController"),
    ):
        hid = GestureHID(hold_bindings={"throttle_up": "w"}, feedback=feedback)
        state = GestureState(hold_actions={"throttle_up"}, mouse_delta=(0, 0))
        hid.apply(state)
        feedback.reset_mock()
        hid.apply(state)  # same hold_actions — no change
    feedback.emit_gesture.assert_not_called()
