import logging
import webrtcvad

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000
_SILENCE_THRESHOLD = 8  # consecutive silent frames before utterance is finalised (160 ms)


class VoiceActivityDetector:
    def __init__(self, aggressiveness: int) -> None:
        self._vad = webrtcvad.Vad(aggressiveness)
        self._buffer: list[bytes] = []
        self._silence_count = 0
        self._in_speech = False

    def process_frame(self, frame: bytes) -> list[bytes] | None:
        try:
            is_speech = self._vad.is_speech(frame, _SAMPLE_RATE)
        except Exception:
            logger.warning("webrtcvad rejected frame (wrong size?), discarding")
            return None

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
