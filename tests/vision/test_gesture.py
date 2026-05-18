from tank_controls.config.loader import VisionConfig
from tank_controls.vision.gesture import HandState, compute_gesture

CONFIG = VisionConfig(quadrant_threshold=0.1, max_mouse_speed=15)


def test_no_hands_returns_empty_state() -> None:
    state = compute_gesture(HandState(None, None), CONFIG)
    assert state.hold_actions == set()
    assert state.mouse_delta == (0, 0)


def test_right_hand_in_deadzone_no_actions() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.75, 0.5)), CONFIG)
    assert state.hold_actions == set()


def test_right_hand_up_throttle_up() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.75, 0.35)), CONFIG)
    assert "throttle_up" in state.hold_actions
    assert "turn_right" not in state.hold_actions
    assert "turn_left" not in state.hold_actions


def test_right_hand_down_throttle_down() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.75, 0.65)), CONFIG)
    assert "throttle_down" in state.hold_actions


def test_right_hand_right_turn_right() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.90, 0.5)), CONFIG)
    assert "turn_right" in state.hold_actions


def test_right_hand_left_turn_left() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.60, 0.5)), CONFIG)
    assert "turn_left" in state.hold_actions


def test_right_hand_diagonal_up_right() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.90, 0.35)), CONFIG)
    assert state.hold_actions == {"throttle_up", "turn_right"}


def test_right_hand_diagonal_down_left() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=(0.60, 0.65)), CONFIG)
    assert state.hold_actions == {"throttle_down", "turn_left"}


def test_left_hand_in_deadzone_zero_delta() -> None:
    state = compute_gesture(HandState(left_wrist=(0.25, 0.5), right_wrist=None), CONFIG)
    assert state.mouse_delta == (0, 0)


def test_left_hand_right_positive_dx() -> None:
    state = compute_gesture(HandState(left_wrist=(0.40, 0.5), right_wrist=None), CONFIG)
    dx, dy = state.mouse_delta
    assert dx > 0
    assert dy == 0


def test_left_hand_up_negative_dy() -> None:
    # up in image coords = lower y value
    state = compute_gesture(HandState(left_wrist=(0.25, 0.35), right_wrist=None), CONFIG)
    dx, dy = state.mouse_delta
    assert dx == 0
    assert dy < 0


def test_left_hand_diagonal_up_right() -> None:
    state = compute_gesture(HandState(left_wrist=(0.40, 0.35), right_wrist=None), CONFIG)
    dx, dy = state.mouse_delta
    assert dx > 0
    assert dy < 0


def test_left_hand_speed_scales_with_distance() -> None:
    near = compute_gesture(HandState(left_wrist=(0.32, 0.5), right_wrist=None), CONFIG)
    far = compute_gesture(HandState(left_wrist=(0.46, 0.5), right_wrist=None), CONFIG)
    assert far.mouse_delta[0] > near.mouse_delta[0]


def test_left_hand_absent_zero_delta() -> None:
    state = compute_gesture(HandState(left_wrist=None, right_wrist=None), CONFIG)
    assert state.mouse_delta == (0, 0)
