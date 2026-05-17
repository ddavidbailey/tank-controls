import asyncio

import sounddevice as sd  # type: ignore[import-untyped]

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20
FRAME_SIZE = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 320 samples per callback


class AudioCapture:
    def __init__(self, queue: asyncio.Queue[bytes], loop: asyncio.AbstractEventLoop) -> None:
        self._queue = queue
        self._loop = loop

    def _put_frame(self, data: bytes) -> None:
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass  # drop stale frame rather than block the event loop

    def _callback(
        self,
        indata: bytes,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        self._loop.call_soon_threadsafe(self._put_frame, bytes(indata))

    def start(self) -> sd.RawInputStream:
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SIZE,
            dtype="int16",
            channels=1,
            callback=self._callback,
        )
        stream.start()
        return stream
