from unittest.mock import patch

from tank_controls.audio.vad import VoiceActivityDetector

# 320 samples × 2 bytes (int16) = 640 bytes per 20ms frame at 16kHz
FRAME = b"\x00" * 640


def make_detector(speech_sequence: list[bool]) -> VoiceActivityDetector:
    """Build a VoiceActivityDetector whose webrtcvad.Vad is mocked.

    speech_sequence controls what is_speech() returns on each call.
    """
    with patch("tank_controls.audio.vad.webrtcvad.Vad") as MockVad:
        MockVad.return_value.is_speech.side_effect = speech_sequence
        detector = VoiceActivityDetector(aggressiveness=2)
    return detector


def test_silence_frames_produce_no_output():
    detector = make_detector([False] * 10)
    results = [detector.process_frame(FRAME) for _ in range(10)]
    assert all(r is None for r in results)


def test_speech_frames_accumulate_without_output():
    detector = make_detector([True] * 5)
    results = [detector.process_frame(FRAME) for _ in range(5)]
    assert all(r is None for r in results)


def test_utterance_returned_after_trailing_silence():
    # 5 speech + 8 silence → utterance emitted on the 13th frame
    detector = make_detector([True] * 5 + [False] * 8)
    results = [detector.process_frame(FRAME) for _ in range(13)]
    assert results[-1] is not None
    assert len(results[-1]) == 13  # 5 speech + 8 silence frames in buffer


def test_partial_silence_does_not_emit():
    # 5 speech + 7 silence → threshold not reached yet
    detector = make_detector([True] * 5 + [False] * 7)
    results = [detector.process_frame(FRAME) for _ in range(12)]
    assert all(r is None for r in results)


def test_resets_after_utterance_second_utterance_detected():
    # Two utterances: 3 speech + 8 silence, then 3 speech + 8 silence
    sequence = [True] * 3 + [False] * 8 + [True] * 3 + [False] * 8
    detector = make_detector(sequence)
    results = [detector.process_frame(FRAME) for _ in range(len(sequence))]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 2
