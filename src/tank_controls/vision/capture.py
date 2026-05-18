import asyncio
import logging
import threading
import time
from typing import Any

import cv2
import numpy as np

from tank_controls.config.loader import VisionConfig

logger = logging.getLogger(__name__)


class FrameCapture:
    def __init__(
        self,
        queue: asyncio.Queue[Any],
        loop: asyncio.AbstractEventLoop,
        config: VisionConfig,
    ) -> None:
        self._queue = queue
        self._loop = loop
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        cap = cv2.VideoCapture(self._config.camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera index {self._config.camera_index}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config.frame_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config.frame_height)
        cap.set(cv2.CAP_PROP_FPS, self._config.fps)
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, args=(cap,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _put_frame(self, frame: np.ndarray) -> None:
        try:
            self._queue.put_nowait(frame)
        except asyncio.QueueFull:
            pass  # drop stale frame; fresh frames are always preferred

    def _capture_loop(self, cap: cv2.VideoCapture) -> None:
        consecutive_failures = 0
        try:
            while self._running:
                ret, frame = cap.read()
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures == 10:
                        logger.warning(
                            "Camera read failed repeatedly — check connection or permissions."
                        )
                    time.sleep(0.01)
                    continue
                consecutive_failures = 0
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._loop.call_soon_threadsafe(self._put_frame, frame_rgb)
        finally:
            cap.release()
