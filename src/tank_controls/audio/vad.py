import numpy as np

_SILENCE_THRESHOLD = 8  # consecutive silent frames before utterance is finalised (160 ms)


class VoiceActivityDetector:
    """Energy-based voice activity detector.

    Compares the RMS amplitude of each 20ms frame against energy_threshold.
    Accumulates speech frames and emits a complete utterance after 8 consecutive
    silent frames (160 ms of trailing silence).
    """

    def __init__(self, energy_threshold: float = 300.0) -> None:
        self._threshold = energy_threshold
        self._buffer: list[bytes] = []
        self._silence_count = 0
        self._in_speech = False

    def process_frame(self, frame: bytes) -> list[bytes] | None:
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        rms = float(np.sqrt(np.mean(samples**2)))
        is_speech = rms > self._threshold

        if is_speech:
            self._in_speech = True
            self._silence_count = 0
            self._buffer.append(frame)
            return None

        if not self._in_speech:
            return None

        self._buffer.append(frame)
        self._silence_count += 1

        if self._silence_count >= _SILENCE_THRESHOLD:
            utterance = list(self._buffer)
            self._buffer = []
            self._silence_count = 0
            self._in_speech = False
            return utterance

        return None
