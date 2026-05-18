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

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                wrist = hand_landmarks.landmark[0]
                # Assign by frame position: left half = drive, right half = turret
                if wrist.x < 0.5:
                    left_wrist = (float(wrist.x), float(wrist.y))
                else:
                    right_wrist = (float(wrist.x), float(wrist.y))

        return HandState(left_wrist=left_wrist, right_wrist=right_wrist)

    def close(self) -> None:
        self._hands.close()
