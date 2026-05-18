import cv2
import numpy as np

from tank_controls.config.loader import VisionConfig
from tank_controls.vision.gesture import GestureState, HandState

_GREEN = (0, 220, 0)
_ORANGE = (0, 140, 255)


def _draw_zones(overlay: np.ndarray, config: VisionConfig) -> None:
    """Draw zone lines, labels, centre dots, and dividing line in-place."""
    h, w = overlay.shape[:2]
    tx = int(w * config.quadrant_threshold)
    ty = int(h * config.quadrant_threshold)
    mid = w // 2
    cy = int(h * 0.5)
    cx_l = int(w * 0.25)
    cx_r = int(w * 0.75)

    # Left half — drive zones (green)
    cv2.line(overlay, (cx_l - tx, 0), (cx_l - tx, h), _GREEN, 1)
    cv2.line(overlay, (cx_l + tx, 0), (cx_l + tx, h), _GREEN, 1)
    cv2.line(overlay, (0, cy - ty), (mid, cy - ty), _GREEN, 1)
    cv2.line(overlay, (0, cy + ty), (mid, cy + ty), _GREEN, 1)
    cv2.putText(overlay, "W+A", (10, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "W", (cx_l - 10, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(
        overlay, "W+D", (cx_l + tx + 4, cy - ty - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1
    )
    cv2.putText(overlay, "A", (10, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "D", (cx_l + tx + 4, cy + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "S+A", (10, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(overlay, "S", (cx_l - 10, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1)
    cv2.putText(
        overlay, "S+D", (cx_l + tx + 4, cy + ty + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, _GREEN, 1
    )
    cv2.circle(overlay, (cx_l, cy), 6, _GREEN, -1)

    # Right half — turret zones (orange)
    cv2.line(overlay, (cx_r - tx, 0), (cx_r - tx, h), _ORANGE, 1)
    cv2.line(overlay, (cx_r + tx, 0), (cx_r + tx, h), _ORANGE, 1)
    cv2.line(overlay, (mid, cy - ty), (w, cy - ty), _ORANGE, 1)
    cv2.line(overlay, (mid, cy + ty), (w, cy + ty), _ORANGE, 1)
    cv2.circle(overlay, (cx_r, cy), 6, _ORANGE, -1)

    # Dividing line
    cv2.line(overlay, (mid, 0), (mid, h), (200, 200, 200), 2)

    # Half labels
    cv2.putText(
        overlay, "DRIVE  (left hand)", (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, _GREEN, 1
    )
    cv2.putText(
        overlay, "TURRET  (right hand)", (mid + 8, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, _ORANGE, 1,
    )


def draw_debug_overlay(
    frame: np.ndarray,
    hand_state: HandState,
    gesture_state: GestureState,
    config: VisionConfig,
) -> np.ndarray:
    """Draw zone overlay plus wrist positions and active action labels (debug mode)."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    _draw_zones(overlay, config)

    # Wrist tracking circles
    if hand_state.right_wrist:
        rx = int(hand_state.right_wrist[0] * w)
        ry = int(hand_state.right_wrist[1] * h)
        cv2.circle(overlay, (rx, ry), 18, _GREEN, 3)
        cv2.putText(
            overlay, "DRIVE", (rx + 22, ry + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _GREEN, 2
        )

    if hand_state.left_wrist:
        lx = int(hand_state.left_wrist[0] * w)
        ly = int(hand_state.left_wrist[1] * h)
        cv2.circle(overlay, (lx, ly), 18, _ORANGE, 3)
        cv2.putText(
            overlay, "TURRET", (lx + 22, ly + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, _ORANGE, 2
        )

    # Active action labels
    y = 26
    if gesture_state.hold_actions:
        text = "Drive: " + " + ".join(sorted(gesture_state.hold_actions))
        cv2.putText(overlay, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, _GREEN, 2)
        y += 28
    if gesture_state.mouse_delta != (0, 0):
        dx, dy = gesture_state.mouse_delta
        cv2.putText(
            overlay, f"Turret: dx={dx:+d} dy={dy:+d}", (10, y),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, _ORANGE, 2,
        )

    return overlay


def draw_overlay_feedback(
    frame: np.ndarray,
    config: VisionConfig,
    paused: bool,
) -> np.ndarray:
    """Draw zone overlay plus LIVE/PAUSED indicator (overlay-feedback mode)."""
    h, w = frame.shape[:2]
    overlay = frame.copy()

    _draw_zones(overlay, config)

    # LIVE / PAUSED indicator — top-right corner
    status_text = "● PAUSED" if paused else "● LIVE"
    status_color = (0, 0, 200) if paused else (0, 200, 0)
    (text_w, _), _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)
    cv2.putText(
        overlay, status_text, (w - text_w - 12, 32),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2,
    )

    return overlay
