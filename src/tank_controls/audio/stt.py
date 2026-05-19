import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import mlx_whisper  # type: ignore[import-untyped]
import numpy as np

# Whisper reliability thresholds (same values used by openai-whisper's own
# hallucination suppression logic).
_NO_SPEECH_THRESHOLD = 0.6   # discard if model thinks there's no speech
_COMPRESSION_THRESHOLD = 2.4  # discard if output is suspiciously repetitive


def _transcribe_sync(model_path: str, audio: np.ndarray, initial_prompt: str) -> str:
    result = mlx_whisper.transcribe(
        audio,
        path_or_hf_repo=model_path,
        initial_prompt=initial_prompt,
        condition_on_previous_text=False,
    )

    segments = result.get("segments") or []
    if segments:
        no_speech = max(s.get("no_speech_prob", 0.0) for s in segments)
        compression = max(s.get("compression_ratio", 1.0) for s in segments)
        if no_speech > _NO_SPEECH_THRESHOLD or compression > _COMPRESSION_THRESHOLD:
            return ""

    return re.sub(r"[^\w\s]", "", str(result.get("text", ""))).lower().strip()


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
        return text
