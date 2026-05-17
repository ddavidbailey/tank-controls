_WINDOW_FRAMES = 75  # 1.5 seconds at 20ms per frame (16kHz, 320 samples each)


class VoiceActivityDetector:
    """Accumulates raw audio frames into 1.5-second chunks for STT.

    Speech detection is delegated to Silero VAD inside faster-whisper's
    transcribe() — this stage just batches frames at a fixed cadence.
    """

    def __init__(self) -> None:
        self._buffer: list[bytes] = []

    def process_frame(self, frame: bytes) -> list[bytes] | None:
        self._buffer.append(frame)
        if len(self._buffer) >= _WINDOW_FRAMES:
            chunk = list(self._buffer)
            self._buffer = []
            return chunk
        return None
