import asyncio
import logging
import queue as _tq

import sounddevice as sd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20
FRAME_SIZE = SAMPLE_RATE * FRAME_DURATION_MS // 1000  # 320 samples per callback


class AudioCapture:
    def __init__(self) -> None:
        self._thread_q: _tq.Queue[bytes] = _tq.Queue(maxsize=20)
        self._callback_fired = False

    def _callback(
        self,
        indata: bytes,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        if not self._callback_fired:
            self._callback_fired = True
            logger.info("Audio callback: PortAudio is delivering frames")
        try:
            self._thread_q.put_nowait(bytes(indata))
        except _tq.Full:
            pass  # drop stale frame rather than block the PortAudio callback

    def start(self, device: "int | None" = None) -> sd.RawInputStream:
        try:
            dev_info = (
                sd.query_devices(device) if device is not None
                else sd.query_devices(kind="input")
            )
            logger.info("Audio capture: using %r", dev_info.get("name", "?"))
        except Exception:
            pass
        stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=FRAME_SIZE,
            dtype="int16",
            channels=1,
            callback=self._callback,
            device=device,
        )
        stream.start()
        logger.info("Audio capture: stream started")
        return stream

    async def pump(self, queue: asyncio.Queue[bytes]) -> None:
        """Drain the thread-safe capture queue into an asyncio queue."""
        logger.info("Audio capture: pump() started — listening for frames")
        first = True
        while True:
            try:
                data = self._thread_q.get_nowait()
                if first:
                    logger.info("Audio capture: first frame in pump() — pipeline active")
                    first = False
                try:
                    queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass
            except _tq.Empty:
                await asyncio.sleep(0.002)
