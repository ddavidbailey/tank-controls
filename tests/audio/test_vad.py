import numpy as np

from tank_controls.audio.vad import VoiceActivityDetector

THRESHOLD = 500.0

# RMS = 0 → silence
SILENCE = np.zeros(320, dtype=np.int16).tobytes()
# RMS = 1000 → clearly above any reasonable threshold
SPEECH = np.full(320, 1000, dtype=np.int16).tobytes()


def test_silence_frames_produce_no_output():
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    results = [detector.process_frame(SILENCE) for _ in range(10)]
    assert all(r is None for r in results)


def test_speech_frames_accumulate_without_output():
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    results = [detector.process_frame(SPEECH) for _ in range(5)]
    assert all(r is None for r in results)


def test_utterance_returned_after_trailing_silence():
    # 5 speech + 8 silence → utterance emitted on the 13th frame
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    frames = [SPEECH] * 5 + [SILENCE] * 8
    results = [detector.process_frame(f) for f in frames]
    assert results[-1] is not None
    assert len(results[-1]) == 13  # 5 speech + 8 silence frames buffered


def test_partial_silence_does_not_emit():
    # 5 speech + 7 silence → threshold not reached yet
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    frames = [SPEECH] * 5 + [SILENCE] * 7
    results = [detector.process_frame(f) for f in frames]
    assert all(r is None for r in results)


def test_resets_after_utterance_second_utterance_detected():
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    sequence = [SPEECH] * 3 + [SILENCE] * 8 + [SPEECH] * 3 + [SILENCE] * 8
    results = [detector.process_frame(f) for f in sequence]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 2
