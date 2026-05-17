from tank_controls.audio.vad import VoiceActivityDetector

FRAME = b"\x00" * 640  # 320 samples × 2 bytes (int16) for 20ms at 16kHz


def test_frames_accumulate_without_output():
    detector = VoiceActivityDetector()
    results = [detector.process_frame(FRAME) for _ in range(74)]
    assert all(r is None for r in results)


def test_chunk_returned_at_75_frames():
    detector = VoiceActivityDetector()
    results = [detector.process_frame(FRAME) for _ in range(75)]
    assert results[-1] is not None
    assert len(results[-1]) == 75


def test_resets_after_chunk():
    detector = VoiceActivityDetector()
    for _ in range(75):
        detector.process_frame(FRAME)
    results = [detector.process_frame(FRAME) for _ in range(74)]
    assert all(r is None for r in results)


def test_chunk_contains_correct_frames():
    detector = VoiceActivityDetector()
    frames = [bytes([i % 256] * 640) for i in range(75)]
    results = [detector.process_frame(f) for f in frames]
    assert results[-1] == frames


def test_two_consecutive_chunks():
    detector = VoiceActivityDetector()
    results = [detector.process_frame(FRAME) for _ in range(150)]
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 2
