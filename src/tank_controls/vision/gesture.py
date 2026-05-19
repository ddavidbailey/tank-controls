from dataclasses import dataclass, field

from tank_controls.config.loader import VisionConfig


@dataclass
class HandState:
    left_wrist: tuple[float, float] | None
    right_wrist: tuple[float, float] | None


@dataclass
class GestureState:
    hold_actions: set[str] = field(default_factory=set)
    mouse_delta: tuple[int, int] = (0, 0)


def compute_gesture(state: HandState, config: VisionConfig) -> GestureState:
    return GestureState(
        hold_actions=_compute_drive(state.right_wrist, config),
        mouse_delta=_compute_turret(state.left_wrist, config),
    )


def _compute_drive(
    wrist: tuple[float, float] | None,
    config: VisionConfig,
) -> set[str]:
    if wrist is None:
        return set()

    dx = wrist[0] - 0.25
    dy = wrist[1] - 0.5  # negative = up in image coords
    t = config.quadrant_threshold

    actions: set[str] = set()
    if dx > t:
        actions.add("turn_right")
    elif dx < -t:
        actions.add("turn_left")
    if dy < -t:
        actions.add("throttle_up")
    elif dy > t:
        actions.add("throttle_down")

    return actions


def _compute_turret(
    wrist: tuple[float, float] | None,
    config: VisionConfig,
) -> tuple[int, int]:
    if wrist is None:
        return (0, 0)

    dx_raw = wrist[0] - 0.75
    dy_raw = wrist[1] - 0.5
    t = config.quadrant_threshold

    def _axis(val: float) -> int:
        if abs(val) < t:
            return 0
        sign = 1.0 if val > 0 else -1.0
        norm = min((abs(val) - t) / (0.5 - t), 1.0)
        return int(sign * (norm ** config.mouse_accel_exponent) * config.max_mouse_speed)

    return (_axis(dx_raw), _axis(dy_raw))
