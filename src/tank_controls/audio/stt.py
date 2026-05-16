import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from faster_whisper import WhisperModel  # type: ignore[import-untyped]


def _transcribe_sync(model: WhisperModel, audio: np.ndarray) -> str:
    segments, _ = model.transcribe(audio)
    return " ".join(seg.text for seg in segments)


class SpeechToText:
    def __init__(self, model: WhisperModel, executor: ThreadPoolExecutor) -> None:
        self._model = model
        self._executor = executor

    async def transcribe(self, frames: list[bytes]) -> str:
        audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        loop = asyncio.get_running_loop()
        text: str = await loop.run_in_executor(self._executor, _transcribe_sync, self._model, audio)
        return re.sub(r"[^\w\s]", "", text).lower().strip()
