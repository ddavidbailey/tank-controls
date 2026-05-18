import logging
import queue as _tq
from typing import Any

from tank_controls.vision.gesture import GestureState

logger = logging.getLogger(__name__)


class FeedbackEmitter:
    def __init__(
        self,
        log: bool = False,
        display_queue: "_tq.Queue[Any] | None" = None,
    ) -> None:
        self._log = log
        self._display_queue = display_queue

    def emit_toggle(self, paused: bool) -> None:
        if self._log:
            logger.info("[PAUSED]" if paused else "[RESUMED]")
        if self._display_queue is not None:
            try:
                self._display_queue.put_nowait({"paused": paused})
            except _tq.Full:
                pass

    def emit_gesture(self, state: GestureState) -> None:
        if self._log and state.hold_actions:
            logger.info("Drive: %s", " + ".join(sorted(state.hold_actions)))
        if self._display_queue is not None:
            try:
                self._display_queue.put_nowait({"state": state})
            except _tq.Full:
                pass
