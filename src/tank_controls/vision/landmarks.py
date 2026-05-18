import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import mediapipe as mp  # type: ignore[import-untyped]
import numpy as np

from tank_controls.vision.gesture import HandState


class HandLandmarker:
    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self._executor = executor
        mp_hands: Any = mp.solutions.hands
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )

    async def detect(self, frame: np.ndarray) -> HandState:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._detect_sync, frame)

    def _detect_sync(self, frame: np.ndarray) -> HandState:
        results = self._hands.process(frame)
        left_wrist: tuple[float, float] | None = None
        right_wrist: tuple[float, float] | None = None

        if results.multi_hand_landmarks and results.multi_handedness:
            for hand_landmarks, handedness in zip(
                results.multi_hand_landmarks, results.multi_handedness
            ):
                label = handedness.classification[0].label  # "Left" or "Right"
                wrist = hand_landmarks.landmark[0]
                coords = (float(wrist.x), float(wrist.y))
                if label == "Left":
                    left_wrist = coords
                else:
                    right_wrist = coords

        return HandState(left_wrist=left_wrist, right_wrist=right_wrist)

    def close(self) -> None:
        self._hands.close()
