import asyncio
import logging
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mediapipe as mp  # type: ignore[import-untyped]
import numpy as np
from mediapipe.tasks import python as mp_python  # type: ignore[import-untyped]
from mediapipe.tasks.python import vision as mp_vision  # type: ignore[import-untyped]

from tank_controls.vision.gesture import HandState

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
)
_MODEL_PATH = Path.home() / ".cache" / "tank-controls" / "hand_landmarker.task"


def _ensure_model() -> Path:
    if not _MODEL_PATH.exists():
        _MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading hand landmarker model to %s ...", _MODEL_PATH)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        logger.info("Model download complete.")
    return _MODEL_PATH


class HandLandmarker:
    def __init__(self, executor: ThreadPoolExecutor) -> None:
        self._executor = executor
        model_path = _ensure_model()
        options = mp_vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp_vision.RunningMode.IMAGE,
            num_hands=2,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)

    async def detect(self, frame: np.ndarray) -> HandState:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._detect_sync, frame)

    def _detect_sync(self, frame: np.ndarray) -> HandState:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
        result = self._landmarker.detect(mp_image)

        left_wrist: tuple[float, float] | None = None
        right_wrist: tuple[float, float] | None = None

        for i, landmarks in enumerate(result.hand_landmarks):
            if i >= len(result.handedness):
                continue
            label = result.handedness[i][0].category_name  # "Left" or "Right"
            wrist = landmarks[0]  # landmark 0 = wrist
            coords = (float(wrist.x), float(wrist.y))
            if label == "Left":
                left_wrist = coords
            else:
                right_wrist = coords

        return HandState(left_wrist=left_wrist, right_wrist=right_wrist)

    def close(self) -> None:
        self._landmarker.close()
