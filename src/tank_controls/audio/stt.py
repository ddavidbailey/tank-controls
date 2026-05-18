import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import mlx_whisper  # type: ignore[import-untyped]
import numpy as np


def _transcribe_sync(model_path: str, audio: np.ndarray, initial_prompt: str) -> str:
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=model_path,
        initial_prompt=initial_prompt,
        condition_on_previous_text=False,
    )
    return str(result.get("text", ""))


class SpeechToText:
    def __init__(
        self,
        model_path: str,
        executor: ThreadPoolExecutor,
        initial_prompt: str = "",
    ) -> None:
        self._model_path = model_path
        self._executor = executor
        self._initial_prompt = initial_prompt

    async def transcribe(self, frames: list[bytes]) -> str:
        audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        loop = asyncio.get_running_loop()
        text: str = await loop.run_in_executor(
            self._executor, _transcribe_sync, self._model_path, audio, self._initial_prompt
        )
        return re.sub(r"[^\w\s]", "", text).lower().strip()
