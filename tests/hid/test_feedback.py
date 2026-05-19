import logging
import queue as _tq

from tank_controls.hid.feedback import FeedbackEmitter
from tank_controls.vision.gesture import GestureState


def test_emit_toggle_paused_logs(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(True)
    assert "[PAUSED]" in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_resumed_logs(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(False)
    assert "[RESUMED]" in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_no_log_when_disabled(caplog: object) -> None:
    emitter = FeedbackEmitter(log=False)
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_toggle(True)
    assert "[PAUSED]" not in caplog.text  # type: ignore[union-attr]


def test_emit_toggle_pushes_to_queue() -> None:
    q: _tq.Queue[object] = _tq.Queue()
    emitter = FeedbackEmitter(log=False, display_queue=q)
    emitter.emit_toggle(True)
    assert q.get_nowait() == {"paused": True}


def test_emit_gesture_logs_actions(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    state = GestureState(hold_actions={"throttle_up", "turn_right"})
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_gesture(state)
    assert "Drive:" in caplog.text  # type: ignore[union-attr]


def test_emit_gesture_no_log_when_empty(caplog: object) -> None:
    emitter = FeedbackEmitter(log=True)
    state = GestureState(hold_actions=set())
    with caplog.at_level(logging.INFO):  # type: ignore[union-attr]
        emitter.emit_gesture(state)
    assert "Drive:" not in caplog.text  # type: ignore[union-attr]


def test_emit_gesture_pushes_to_queue() -> None:
    q: _tq.Queue[object] = _tq.Queue()
    emitter = FeedbackEmitter(log=False, display_queue=q)
    state = GestureState(hold_actions={"throttle_up"})
    emitter.emit_gesture(state)
    msg = q.get_nowait()
    assert msg == {"state": state}  # type: ignore[comparison-overlap]


def test_emit_gesture_pushes_to_queue_when_empty() -> None:
    q: _tq.Queue[object] = _tq.Queue()
    emitter = FeedbackEmitter(log=False, display_queue=q)
    state = GestureState(hold_actions=set())
    emitter.emit_gesture(state)
    msg = q.get_nowait()
    assert msg == {"state": state}  # type: ignore[comparison-overlap]


def test_queue_full_does_not_raise() -> None:
    q: _tq.Queue[object] = _tq.Queue(maxsize=1)
    q.put_nowait({"paused": True})
    emitter = FeedbackEmitter(log=False, display_queue=q)
    emitter.emit_toggle(False)  # should not raise
