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
        hold_actions=_compute_drive(state.left_wrist, config),
        mouse_delta=_compute_turret(state.right_wrist, config),
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

    mouse_x = 0 if abs(dx_raw) < t else int((dx_raw / 0.5) * config.max_mouse_speed)
    mouse_y = 0 if abs(dy_raw) < t else int((dy_raw / 0.5) * config.max_mouse_speed)

    return (mouse_x, mouse_y)
