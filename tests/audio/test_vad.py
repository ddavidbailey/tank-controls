import numpy as np

from tank_controls.audio.vad import VoiceActivityDetector, _MIN_SPEECH_FRAMES

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
    results = [detector.process_frame(SPEECH) for _ in range(_MIN_SPEECH_FRAMES)]
    assert all(r is None for r in results)


def test_utterance_returned_after_trailing_silence():
    # _MIN_SPEECH_FRAMES speech + 8 silence → utterance emitted on the last frame
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    frames = [SPEECH] * _MIN_SPEECH_FRAMES + [SILENCE] * 8
    results = [detector.process_frame(f) for f in frames]
    assert results[-1] is not None
    assert len(results[-1]) == _MIN_SPEECH_FRAMES + 8


def test_partial_silence_does_not_emit():
    # _MIN_SPEECH_FRAMES speech + 7 silence → trailing-silence threshold not reached yet
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    frames = [SPEECH] * _MIN_SPEECH_FRAMES + [SILENCE] * 7
    results = [detector.process_frame(f) for f in frames]
    assert all(r is None for r in results)


def test_short_noise_burst_discarded():
    # Fewer than _MIN_SPEECH_FRAMES speech frames → utterance suppressed (noise guard)
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    frames = [SPEECH] * (_MIN_SPEECH_FRAMES - 1) + [SILENCE] * 8
    results = [detector.process_frame(f) for f in frames]
    # The VAD completes the utterance window but returns None (not enough speech)
    assert all(r is None for r in results)


def test_resets_after_utterance_second_utterance_detected():
    detector = VoiceActivityDetector(energy_threshold=THRESHOLD)
    sequence = (
        [SPEECH] * _MIN_SPEECH_FRAMES + [SILENCE] * 8
        + [SPEECH] * _MIN_SPEECH_FRAMES + [SILENCE] * 8
    )
    results = [detector.process_frame(f) for f in sequence]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 2
